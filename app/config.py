from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union
import os

class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra='ignore'
    )
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False
    
    # Ollama backends - comma-separated string from env, parsed to list
    ollama_servers: Union[str, List[str]] = "http://localhost:11434"
    
    @field_validator('ollama_servers', mode='before')
    @classmethod
    def parse_ollama_servers(cls, v):
        """Parse comma-separated Ollama server URLs from environment"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return ["http://localhost:11434"]
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./tokamak_ai_api.db"
    
    # Security
    secret_key: str = "your-secret-key-change-this"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 43200  # 30 days
    
    # Rate limiting
    default_rate_limit: int = 1000
    rate_limit_window: int = 3600  # 1 hour in seconds
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "/var/log/tokamak-ai-api/server.log"
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090

settings = Settings()
