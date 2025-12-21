import httpx
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import asyncio
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class ServerStatus:
    def __init__(self, url: str):
        self.url = url
        self.is_healthy = True
        self.last_check = datetime.now(timezone.utc)
        self.fail_count = 0
        self.success_count = 0
        self.response_time_ms = 0
        self.current_load = 0  # Number of active requests
    
    def mark_success(self, response_time_ms: int):
        """Mark a successful request"""
        self.is_healthy = True
        self.fail_count = 0
        self.success_count += 1
        self.response_time_ms = response_time_ms
        self.last_check = datetime.now(timezone.utc)
    
    def mark_failure(self):
        """Mark a failed request"""
        self.fail_count += 1
        self.last_check = datetime.now(timezone.utc)
        
        # Mark as unhealthy after 3 consecutive failures
        if self.fail_count >= 3:
            self.is_healthy = False
            logger.warning(f"Server {self.url} marked as unhealthy after {self.fail_count} failures")

class LoadBalancer:
    def __init__(self):
        self.servers: List[ServerStatus] = []
        self.current_index = 0
        self.health_check_task = None
        
        # Initialize servers from config
        self._update_servers_from_config()
        
        logger.info(f"Load balancer initialized with {len(self.servers)} servers")
    
    def _update_servers_from_config(self):
        """Update server list from config, adding new servers if needed"""
        config_servers = set(settings.ollama_servers)
        existing_servers = {s.url for s in self.servers}
        
        # Add new servers
        for server_url in config_servers:
            if server_url not in existing_servers:
                self.servers.append(ServerStatus(server_url))
                logger.info(f"Added new server to load balancer: {server_url}")
        
        # Remove servers that are no longer in config (optional - keep for now)
        # This allows graceful removal of servers
    
    async def start_health_checks(self):
        """Start periodic health checks"""
        self.health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop_health_checks(self):
        """Stop health checks"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
    
    async def _health_check_loop(self):
        """Periodic health check for all servers"""
        # Do an immediate check on startup
        await self._check_all_servers()
        
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._check_all_servers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_all_servers(self):
        """Check health of all servers"""
        # Update server list from config in case it changed
        self._update_servers_from_config()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for server in self.servers:
                try:
                    start_time = datetime.now(timezone.utc)
                    response = await client.get(f"{server.url}/api/tags")
                    
                    if response.status_code == 200:
                        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                        server.mark_success(int(response_time))
                        
                        if not server.is_healthy:
                            logger.info(f"Server {server.url} is back online")
                    else:
                        server.mark_failure()
                        logger.warning(f"Health check failed for {server.url}: HTTP {response.status_code}")
                        
                except Exception as e:
                    server.mark_failure()
                    logger.warning(f"Health check failed for {server.url}: {e}")
    
    def get_next_server(self) -> Optional[ServerStatus]:
        """
        Get next available server using least connections algorithm
        """
        # Filter healthy servers
        healthy_servers = [s for s in self.servers if s.is_healthy]
        
        if not healthy_servers:
            logger.error("No healthy servers available!")
            return None
        
        # Use least connections algorithm
        selected_server = min(healthy_servers, key=lambda s: s.current_load)
        
        return selected_server
    
    def get_server_by_round_robin(self) -> Optional[ServerStatus]:
        """
        Get next server using round-robin algorithm
        """
        healthy_servers = [s for s in self.servers if s.is_healthy]
        
        if not healthy_servers:
            return None
        
        # Round robin selection
        server = healthy_servers[self.current_index % len(healthy_servers)]
        self.current_index += 1
        
        return server
    
    async def proxy_request(
        self,
        method: str,
        path: str,
        json_data: dict = None,
        stream: bool = False
    ) -> Tuple[httpx.Response, str]:
        """
        Proxy request to backend server with automatic failover
        Returns: (response, server_url_used)
        """
        # Update server list from config before making request
        self._update_servers_from_config()
        
        max_retries = len(self.servers)
        last_exception = None
        
        for attempt in range(max_retries):
            server = self.get_next_server()
            
            if not server:
                # If no healthy servers, try all servers once
                if attempt == 0:
                    logger.warning("No healthy servers, trying all servers anyway")
                    all_servers = [s for s in self.servers]
                    if all_servers:
                        server = all_servers[attempt % len(all_servers)]
                    else:
                        raise Exception("No servers configured")
                else:
                    raise Exception("No healthy servers available")
            
            # Increment load counter
            server.current_load += 1
            server_url_used = server.url  # Store the server URL used
            
            try:
                url = f"{server.url}{path}"
                
                async with httpx.AsyncClient(timeout=300.0) as client:
                    start_time = datetime.now(timezone.utc)
                    
                    if stream:
                        # For streaming requests
                        response = await client.request(
                            method=method,
                            url=url,
                            json=json_data
                        )
                    else:
                        response = await client.request(
                            method=method,
                            url=url,
                            json=json_data
                        )
                    
                    # Calculate response time
                    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    
                    # Mark success
                    server.mark_success(int(response_time))
                    
                    # Decrement load counter
                    server.current_load -= 1
                    
                    return (response, server_url_used)
                    
            except Exception as e:
                logger.warning(f"Request to {server.url}{path} failed: {e}")
                server.mark_failure()
                server.current_load -= 1
                last_exception = e
                
                # Try next server
                continue
        
        # All servers failed
        raise Exception(f"All backend servers failed. Last error: {last_exception}")
    
    def get_status(self) -> dict:
        """Get status of all servers"""
        return {
            "total_servers": len(self.servers),
            "healthy_servers": sum(1 for s in self.servers if s.is_healthy),
            "servers": [
                {
                    "url": s.url,
                    "healthy": s.is_healthy,
                    "current_load": s.current_load,
                    "success_count": s.success_count,
                    "fail_count": s.fail_count,
                    "response_time_ms": s.response_time_ms,
                    "last_check": s.last_check.isoformat()
                }
                for s in self.servers
            ]
        }

# Global load balancer instance
load_balancer = LoadBalancer()
