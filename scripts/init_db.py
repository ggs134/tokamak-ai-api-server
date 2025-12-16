#!/usr/bin/env python3
"""
Initialize the database schema
Usage: python init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try importing from app module, fallback to direct import
try:
    from app.database import init_db, engine, AsyncSessionLocal, APIKey, generate_api_key, hash_api_key
except ImportError:
    # If app module doesn't exist, import directly
    from app.database import init_db, engine, AsyncSessionLocal, APIKey, generate_api_key, hash_api_key

from datetime import datetime, timezone
from sqlalchemy import select

async def create_admin_if_not_exists():
    """Create default admin user if none exists"""
    
    async with AsyncSessionLocal() as session:
        # Check if any admin exists
        result = await session.execute(
            select(APIKey).where(APIKey.role == "admin")
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            # Create default admin
            api_key = generate_api_key()
            api_key_hash = hash_api_key(api_key)
            
            admin_key = APIKey(
                api_key_hash=api_key_hash,
                username="admin",
                role="admin",
                rate_limit=10000,
                description="Default admin account",
                created_at=datetime.now(timezone.utc)
            )
            
            session.add(admin_key)
            await session.commit()
            
            print("\n" + "="*60)
            print("Default Admin Account Created!")
            print("="*60)
            print(f"Username:    admin")
            print(f"Role:        admin")
            print(f"Rate Limit:  10000 requests/hour")
            print(f"API Key:     {api_key}")
            print("="*60)
            print("\nIMPORTANT: Save this admin API key securely!")
            print()
        else:
            print("Admin account already exists. Skipping creation.")

async def main():
    print("Initializing database...")
    
    try:
        # Create tables
        await init_db()
        print("✓ Database tables created successfully")
        
        # Create default admin
        await create_admin_if_not_exists()
        
        print("\nDatabase initialization complete!")
        
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Close database engine
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
