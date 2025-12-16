from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, BigInteger, Index
from datetime import datetime, timedelta, timezone
from app.config import settings
import secrets
import hashlib

Base = declarative_base()

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_hash = Column(String(64), unique=True, index=True, nullable=False)
    username = Column(String(100), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    rate_limit = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=True)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(100), index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    model = Column(String(100), nullable=False)
    endpoint = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    server_used = Column(String(200), nullable=True)

class RateLimit(Base):
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    count = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_username_window', 'username', 'window_start', unique=True),
    )

# Database engine
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False}  # SQLite specific
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key(prefix: str = "sk") -> str:
    """Generate a new API key"""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}-{random_part}"
