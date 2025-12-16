from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from app.config import settings
from app.models import User
from app.database import RateLimit
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self._cleanup_task = None
    
    async def connect(self):
        """Initialize rate limiter (no-op for SQLite)"""
        logger.info("Rate limiter initialized (SQLite-based)")
    
    async def close(self):
        """Cleanup rate limiter (no-op for SQLite)"""
        pass
    
    async def _cleanup_expired_limits(self, db: AsyncSession):
        """Remove expired rate limit records"""
        try:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                delete(RateLimit).where(RateLimit.expires_at < now)
            )
            await db.commit()
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.debug(f"Cleaned up {deleted_count} expired rate limit records")
        except Exception as e:
            logger.error(f"Error cleaning up expired rate limits: {e}")
            await db.rollback()
    
    async def check_rate_limit(self, user: User, db: AsyncSession) -> bool:
        """
        Check if user has exceeded rate limit
        Returns True if within limit, raises HTTPException if exceeded
        """
        now = datetime.utcnow()
        # Round down to the start of the current window (hour)
        window_start = now.replace(minute=0, second=0, microsecond=0)
        expires_at = window_start + timedelta(seconds=settings.rate_limit_window)
        
        try:
            # Clean up expired records periodically (every 100 requests)
            if hash(user.username) % 100 == 0:
                await self._cleanup_expired_limits(db)
            
            # Get or create rate limit record
            result = await db.execute(
                select(RateLimit).where(
                    and_(
                        RateLimit.username == user.username,
                        RateLimit.window_start == window_start
                    )
                )
            )
            rate_limit = result.scalar_one_or_none()
            
            if not rate_limit:
                # Create new rate limit record
                rate_limit = RateLimit(
                    username=user.username,
                    window_start=window_start,
                    count=1,
                    expires_at=expires_at
                )
                db.add(rate_limit)
            else:
                # Increment existing counter
                rate_limit.count += 1
            
            # Check if limit exceeded
            if rate_limit.count > user.rate_limit:
                remaining_seconds = int((expires_at - now).total_seconds())
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {remaining_seconds} seconds.",
                    headers={"Retry-After": str(remaining_seconds)}
                )
            
            await db.commit()
            return True
            
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            await db.rollback()
            # On error, allow the request to proceed
            return True
    
    async def get_usage_count(self, username: str, db: AsyncSession) -> int:
        """Get current usage count for a user"""
        now = datetime.utcnow()
        window_start = now.replace(minute=0, second=0, microsecond=0)
        
        try:
            result = await db.execute(
                select(RateLimit).where(
                    and_(
                        RateLimit.username == username,
                        RateLimit.window_start == window_start
                    )
                )
            )
            rate_limit = result.scalar_one_or_none()
            return rate_limit.count if rate_limit else 0
        except Exception as e:
            logger.error(f"Error getting usage count: {e}")
            return 0
    
    async def reset_user_limit(self, username: str, db: AsyncSession):
        """Reset rate limit for a specific user (admin function)"""
        now = datetime.utcnow()
        window_start = now.replace(minute=0, second=0, microsecond=0)
        
        try:
            result = await db.execute(
                delete(RateLimit).where(
                    and_(
                        RateLimit.username == username,
                        RateLimit.window_start == window_start
                    )
                )
            )
            await db.commit()
            logger.info(f"Rate limit reset for user: {username}")
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            await db.rollback()

# Global rate limiter instance
rate_limiter = RateLimiter()
