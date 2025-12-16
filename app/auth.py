from fastapi import HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone
from app.database import APIKey, get_db, hash_api_key
from app.models import User, UserRole
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify API key and return user information
    """
    api_key = credentials.credentials
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    
    # Hash the provided API key
    api_key_hash = hash_api_key(api_key)
    
    # Query database for the API key
    result = await db.execute(
        select(APIKey).where(APIKey.api_key_hash == api_key_hash)
    )
    key_record = result.scalar_one_or_none()
    
    if not key_record:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    if not key_record.is_active:
        logger.warning(f"Inactive API key used: {key_record.username}")
        raise HTTPException(
            status_code=403,
            detail="API key is inactive"
        )
    
    # Update last used timestamp
    await db.execute(
        update(APIKey)
        .where(APIKey.api_key_hash == api_key_hash)
        .values(last_used_at=datetime.now(timezone.utc))
    )
    await db.commit()
    
    # Return user information
    return User(
        username=key_record.username,
        role=UserRole(key_record.role),
        rate_limit=key_record.rate_limit,
        is_active=key_record.is_active,
        created_at=key_record.created_at,
        last_used_at=key_record.last_used_at
    )

async def verify_admin(user: User = Depends(verify_api_key)) -> User:
    """
    Verify that the user has admin role
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user

async def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get user if authorization header is provided, otherwise return None
    Used for optional authentication endpoints
    """
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    api_key = authorization.replace("Bearer ", "")
    api_key_hash = hash_api_key(api_key)
    
    result = await db.execute(
        select(APIKey).where(APIKey.api_key_hash == api_key_hash)
    )
    key_record = result.scalar_one_or_none()
    
    if not key_record or not key_record.is_active:
        return None
    
    return User(
        username=key_record.username,
        role=UserRole(key_record.role),
        rate_limit=key_record.rate_limit,
        is_active=key_record.is_active,
        created_at=key_record.created_at,
        last_used_at=key_record.last_used_at
    )
