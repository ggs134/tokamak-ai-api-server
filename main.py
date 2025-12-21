from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import logging
import json
import time
import asyncio

from app.config import settings
from app.models import (
    OllamaGenerateRequest, OllamaChatRequest, 
    HealthResponse, ErrorResponse, UsageRecord,
    APIKeyCreate, APIKeyResponse, UsageStats, User
)
from app.auth import verify_api_key, verify_admin, get_optional_user
from app.rate_limiter import rate_limiter
from app.load_balancer import load_balancer
from app.database import get_db, init_db, APIKey, UsageLog, generate_api_key, hash_api_key
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Tokamak AI API Server...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize rate limiter
    await rate_limiter.connect()
    
    # Log configured servers
    logger.info(f"Configured Ollama servers: {settings.ollama_servers}")
    logger.info(f"Load balancer has {len(load_balancer.servers)} servers")
    for i, server in enumerate(load_balancer.servers, 1):
        logger.info(f"  Server {i}: {server.url}")
    
    # Start health checks
    await load_balancer.start_health_checks()
    
    # Log initial server status after health check
    await asyncio.sleep(2)  # Wait for initial health check
    status = load_balancer.get_status()
    logger.info(f"Server status after startup: {status['healthy_servers']}/{status['total_servers']} healthy")
    for server_info in status['servers']:
        health_status = "healthy" if server_info['healthy'] else "unhealthy"
        logger.info(f"  {server_info['url']}: {health_status} (fail_count: {server_info.get('fail_count', 0)})")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tokamak AI API Server...")
    await rate_limiter.close()
    await load_balancer.stop_health_checks()

# Security scheme for Swagger UI
from fastapi.openapi.utils import get_openapi

security_scheme = HTTPBearer(
    scheme_name="HTTPBearer",
    description="API Key를 입력하세요. 데이터베이스에 등록된 유효한 API Key만 사용할 수 있습니다."
)

app = FastAPI(
    title="Tokamak AI API Server",
    description="Authenticated and load-balanced AI API server for Tokamak Network",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "onComplete": """
        function() {
            // API 키 입력 후 자동으로 검증
            const authBtn = document.querySelector('.btn.authorize');
            if (authBtn) {
                authBtn.addEventListener('click', function() {
                    setTimeout(function() {
                        const authModal = document.querySelector('.auth-container');
                        if (authModal) {
                            const input = authModal.querySelector('input[type="password"]');
                            if (input) {
                                input.addEventListener('blur', function() {
                                    const apiKey = this.value;
                                    if (apiKey && apiKey.startsWith('sk-')) {
                                        // API 키 검증
                                        fetch('/auth/verify', {
                                            method: 'GET',
                                            headers: {
                                                'Authorization': 'Bearer ' + apiKey
                                            }
                                        })
                                        .then(response => {
                                            if (response.ok) {
                                                return response.json();
                                            } else {
                                                throw new Error('Invalid API key');
                                            }
                                        })
                                        .then(data => {
                                            console.log('API key verified:', data);
                                        })
                                        .catch(error => {
                                            alert('유효하지 않은 API 키입니다. 데이터베이스에 등록된 키만 사용할 수 있습니다.');
                                            this.value = '';
                                        });
                                    }
                                });
                            }
                        }
                    }, 100);
                });
            }
        }
        """
    }
)

# Custom OpenAPI schema with security definitions
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "⚠️ 중요: 데이터베이스에 등록된 유효한 API Key만 사용할 수 있습니다. 등록되지 않은 키를 입력하면 API 요청 시 403 Forbidden 오류가 발생합니다. 키를 입력한 후 /auth/verify 엔드포인트를 호출하여 검증할 수 있습니다."
        }
    }
    
    # Add security requirement to protected endpoints
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            # Skip public endpoints
            if path in ["/health", "/auth/verify", "/api/tags"] or method.lower() == "options":
                continue
            # Add security requirement if endpoint requires auth
            if "security" not in details:
                details["security"] = [{"HTTPBearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration:.2f}ms"
    )
    
    return response

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.now(timezone.utc)
        ).dict()
    )

# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================

@app.get("/auth/verify", tags=["Authentication"])
async def verify_auth(
    user: User = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    API 키 검증 엔드포인트
    
    Swagger UI의 authorize 버튼에서 API 키를 입력한 후,
    이 엔드포인트를 호출하여 키가 유효한지 확인할 수 있습니다.
    등록되지 않은 키를 사용하면 403 Forbidden 오류가 발생합니다.
    """
    return {
        "valid": True,
        "username": user.username,
        "role": user.role.value,
        "rate_limit": user.rate_limit,
        "is_active": user.is_active,
        "message": "API 키가 유효합니다."
    }

@app.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint"""
    
    # Check database
    db_ok = True
    try:
        await db.execute(select(1))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_ok = False
    
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        ollama_servers=load_balancer.get_status()["servers"],
        database_connected=db_ok
    )

@app.get("/status")
async def get_status(user: User = Depends(verify_admin)):
    """Get detailed server status (admin only)"""
    return {
        "load_balancer": load_balancer.get_status(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ============================================================================
# API KEY MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/admin/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    key_request: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Create a new API key (admin only)"""
    
    # Generate new API key
    new_api_key = generate_api_key()
    api_key_hash = hash_api_key(new_api_key)
    
    # Create database record
    db_key = APIKey(
        api_key_hash=api_key_hash,
        username=key_request.username,
        role=key_request.role.value,
        rate_limit=key_request.rate_limit,
        description=key_request.description,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)
    
    logger.info(f"API key created for user: {key_request.username} by admin: {admin.username}")
    
    return APIKeyResponse(
        api_key=new_api_key,
        username=db_key.username,
        role=db_key.role,
        rate_limit=db_key.rate_limit,
        created_at=db_key.created_at,
        description=db_key.description
    )

@app.get("/admin/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """List all API keys (admin only)"""
    
    result = await db.execute(select(APIKey))
    keys = result.scalars().all()
    
    return {
        "keys": [
            {
                "username": k.username,
                "role": k.role,
                "rate_limit": k.rate_limit,
                "is_active": k.is_active,
                "created_at": k.created_at.isoformat(),
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "description": k.description
            }
            for k in keys
        ]
    }

@app.delete("/admin/api-keys/{username}")
async def revoke_api_key(
    username: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Revoke an API key (admin only)"""
    
    result = await db.execute(
        select(APIKey).where(APIKey.username == username)
    )
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    await db.delete(key)
    await db.commit()
    
    logger.info(f"API key revoked for user: {username} by admin: {admin.username}")
    
    return {"message": f"API key for {username} has been revoked"}

# ============================================================================
# OLLAMA API ENDPOINTS
# ============================================================================

async def log_usage(
    db: AsyncSession,
    username: str,
    model: str,
    endpoint: str,
    prompt_tokens: int,
    completion_tokens: Optional[int],
    duration_ms: Optional[int],
    success: bool,
    error: Optional[str],
    server_used: Optional[str]
):
    """Log API usage to database"""
    try:
        usage_log = UsageLog(
            username=username,
            timestamp=datetime.now(timezone.utc),
            model=model,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + (completion_tokens or 0),
            duration_ms=duration_ms,
            success=success,
            error=error,
            server_used=server_used
        )
        db.add(usage_log)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log usage: {e}")

@app.post("/api/generate")
async def generate(
    request: OllamaGenerateRequest,
    user: User = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Generate completion from a prompt"""
    
    # Check rate limit
    await rate_limiter.check_rate_limit(user, db)
    
    start_time = time.time()
    success = True
    error_msg = None
    server_url = None
    
    try:
        # Proxy request to backend
        if request.stream:
            # Streaming response
            response, server_url = await load_balancer.proxy_request(
                method="POST",
                path="/api/generate",
                json_data=request.dict(),
                stream=True
            )
            
            async def generate_stream():
                async for chunk in response.aiter_bytes():
                    yield chunk
            
            # Log usage (approximate for streaming)
            prompt_tokens = len(request.prompt.split())
            duration_ms = int((time.time() - start_time) * 1000)
            
            await log_usage(
                db=db,
                username=user.username,
                model=request.model,
                endpoint="generate",
                prompt_tokens=prompt_tokens,
                completion_tokens=None,
                duration_ms=duration_ms,
                success=True,
                error=None,
                server_used=server_url
            )
            
            return StreamingResponse(
                generate_stream(),
                media_type="application/x-ndjson"
            )
        else:
            # Non-streaming response
            response, server_url = await load_balancer.proxy_request(
                method="POST",
                path="/api/generate",
                json_data=request.dict(),
                stream=False
            )
            
            result = response.json()
            
            # Log usage
            prompt_tokens = len(request.prompt.split())
            completion_tokens = len(result.get("response", "").split()) if "response" in result else 0
            duration_ms = int((time.time() - start_time) * 1000)
            
            await log_usage(
                db=db,
                username=user.username,
                model=request.model,
                endpoint="generate",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                success=True,
                error=None,
                server_used=server_url
            )
            
            return result
            
    except Exception as e:
        success = False
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log failed request
        await log_usage(
            db=db,
            username=user.username,
            model=request.model,
            endpoint="generate",
            prompt_tokens=len(request.prompt.split()),
            completion_tokens=None,
            duration_ms=duration_ms,
            success=False,
            error=error_msg,
            server_used=server_url
        )
        
        raise HTTPException(status_code=503, detail=f"Backend error: {error_msg}")

@app.post("/api/chat")
async def chat(
    request: OllamaChatRequest,
    user: User = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Chat with a model"""
    
    # Check rate limit
    await rate_limiter.check_rate_limit(user, db)
    
    start_time = time.time()
    server_url = None
    
    try:
        if request.stream:
            # Streaming response
            response, server_url = await load_balancer.proxy_request(
                method="POST",
                path="/api/chat",
                json_data=request.dict(),
                stream=True
            )
            
            async def generate_stream():
                async for chunk in response.aiter_bytes():
                    yield chunk
            
            # Log usage
            total_content = " ".join([msg.content for msg in request.messages])
            prompt_tokens = len(total_content.split())
            duration_ms = int((time.time() - start_time) * 1000)
            
            await log_usage(
                db=db,
                username=user.username,
                model=request.model,
                endpoint="chat",
                prompt_tokens=prompt_tokens,
                completion_tokens=None,
                duration_ms=duration_ms,
                success=True,
                error=None,
                server_used=server_url
            )
            
            return StreamingResponse(
                generate_stream(),
                media_type="application/x-ndjson"
            )
        else:
            # Non-streaming response
            response, server_url = await load_balancer.proxy_request(
                method="POST",
                path="/api/chat",
                json_data=request.dict(),
                stream=False
            )
            
            result = response.json()
            
            # Log usage
            total_content = " ".join([msg.content for msg in request.messages])
            prompt_tokens = len(total_content.split())
            
            if "message" in result and "content" in result["message"]:
                completion_tokens = len(result["message"]["content"].split())
            else:
                completion_tokens = 0
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            await log_usage(
                db=db,
                username=user.username,
                model=request.model,
                endpoint="chat",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                success=True,
                error=None,
                server_used=server_url
            )
            
            return result
            
    except Exception as e:
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log failed request
        total_content = " ".join([msg.content for msg in request.messages])
        await log_usage(
            db=db,
            username=user.username,
            model=request.model,
            endpoint="chat",
            prompt_tokens=len(total_content.split()),
            completion_tokens=None,
            duration_ms=duration_ms,
            success=False,
            error=error_msg,
            server_used=server_url
        )
        
        raise HTTPException(status_code=503, detail=f"Backend error: {error_msg}")

@app.get("/api/tags")
async def list_models(user: Optional[User] = Depends(get_optional_user)):
    """List available models from all healthy servers"""
    
    # Get all healthy servers (or all servers if none are healthy)
    healthy_servers = [s for s in load_balancer.servers if s.is_healthy]
    
    if not healthy_servers:
        # If no healthy servers, try all servers anyway
        healthy_servers = load_balancer.servers
        if not healthy_servers:
            raise HTTPException(status_code=503, detail="No servers configured")
    
    # Collect models from all servers
    all_models = []
    model_map = {}  # Track unique models by name to avoid duplicates
    
    async def fetch_models_from_server(server_url: str) -> tuple[str, list]:
        """Fetch models from a single server"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{server_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return (server_url, data.get("models", []))
                return (server_url, [])
        except Exception as e:
            logger.warning(f"Failed to get models from {server_url}: {e}")
            return (server_url, [])
    
    # Fetch from all servers in parallel
    tasks = [fetch_models_from_server(server.url) for server in healthy_servers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in results:
        if isinstance(result, Exception):
            continue
        if not result:
            continue
            
        server_url, server_models = result
        
        # Add models with server info
        for model in server_models:
            model_name = model.get("name", "")
            if model_name:
                if model_name not in model_map:
                    # First time seeing this model
                    model_with_server = model.copy()
                    model_with_server["server"] = server_url
                    model_map[model_name] = model_with_server
                    all_models.append(model_with_server)
                else:
                    # Model already exists, add server to available servers list
                    existing = model_map[model_name]
                    if "servers" not in existing:
                        existing["servers"] = [existing.get("server", "")]
                    if server_url not in existing["servers"]:
                        existing["servers"].append(server_url)
    
    if not all_models:
        raise HTTPException(status_code=503, detail="Failed to retrieve models from any server")
    
    return {"models": all_models}

# ============================================================================
# USAGE STATISTICS ENDPOINTS
# ============================================================================

@app.get("/usage/me")
async def get_my_usage(
    user: User = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Get usage statistics for current user"""
    
    # Get usage from current hour
    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.username == user.username)
        .order_by(UsageLog.timestamp.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    
    # Get current rate limit usage
    current_usage = await rate_limiter.get_usage_count(user.username, db)
    
    return {
        "username": user.username,
        "rate_limit": user.rate_limit,
        "current_hour_usage": current_usage,
        "remaining": user.rate_limit - current_usage,
        "recent_requests": [
            {
                "timestamp": log.timestamp.isoformat(),
                "model": log.model,
                "endpoint": log.endpoint,
                "tokens": log.total_tokens,
                "duration_ms": log.duration_ms,
                "success": log.success
            }
            for log in logs[:20]  # Last 20 requests
        ]
    }

@app.get("/admin/usage/{username}")
async def get_user_usage(
    username: str,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """Get usage statistics for a specific user (admin only)"""
    
    from datetime import timedelta
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db.execute(
        select(UsageLog)
        .where(and_(
            UsageLog.username == username,
            UsageLog.timestamp >= start_date
        ))
        .order_by(UsageLog.timestamp.desc())
    )
    logs = result.scalars().all()
    
    if not logs:
        return {
            "username": username,
            "period_days": days,
            "total_requests": 0,
            "message": "No usage data found"
        }
    
    total_requests = len(logs)
    successful_requests = sum(1 for log in logs if log.success)
    failed_requests = total_requests - successful_requests
    total_tokens = sum(log.total_tokens for log in logs)
    
    # Find most used model
    model_counts = {}
    for log in logs:
        model_counts[log.model] = model_counts.get(log.model, 0) + 1
    most_used_model = max(model_counts.items(), key=lambda x: x[1])[0] if model_counts else None
    
    return {
        "username": username,
        "period_days": days,
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "total_tokens": total_tokens,
        "avg_tokens_per_request": total_tokens / total_requests if total_requests > 0 else 0,
        "most_used_model": most_used_model,
        "model_usage": model_counts,
        "period_start": start_date.isoformat(),
        "period_end": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )
