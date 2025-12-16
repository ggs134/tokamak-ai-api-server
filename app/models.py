from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

class APIKeyCreate(BaseModel):
    username: str
    role: UserRole = UserRole.USER
    rate_limit: int = 1000
    description: Optional[str] = None

class APIKeyResponse(BaseModel):
    api_key: str
    username: str
    role: str
    rate_limit: int
    created_at: datetime
    description: Optional[str] = None

class User(BaseModel):
    username: str
    role: UserRole
    rate_limit: int
    is_active: bool = True
    created_at: datetime
    last_used_at: Optional[datetime] = None

class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: Optional[Dict[str, Any]] = None
    system: Optional[str] = None
    template: Optional[str] = None
    context: Optional[List[int]] = None
    raw: bool = False

class OllamaChatMessage(BaseModel):
    role: str
    content: str
    images: Optional[List[str]] = None

class OllamaChatRequest(BaseModel):
    model: str
    messages: List[OllamaChatMessage]
    stream: bool = False
    options: Optional[Dict[str, Any]] = None

class UsageRecord(BaseModel):
    username: str
    timestamp: datetime
    model: str
    endpoint: str
    prompt_tokens: int
    completion_tokens: Optional[int] = None
    total_tokens: int
    duration_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None

class UsageStats(BaseModel):
    username: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    avg_tokens_per_request: float
    most_used_model: Optional[str] = None
    period_start: datetime
    period_end: datetime

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    ollama_servers: List[Dict[str, Any]]
    database_connected: bool

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime
