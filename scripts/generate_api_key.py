#!/usr/bin/env python3
"""
Script to generate API keys for users
Usage: python scripts/generate_api_key.py <username> [--role admin|user] [--rate-limit 1000]
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, APIKey, generate_api_key, hash_api_key
from app.models import UserRole
from datetime import datetime, timezone

async def create_api_key(
    username: str,
    role: str = "user",
    rate_limit: int = 1000,
    description: str = None
):
    """Create a new API key"""
    
    # Generate new API key
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)
    
    async with AsyncSessionLocal() as session:
        # Create database record
        db_key = APIKey(
            api_key_hash=api_key_hash,
            username=username,
            role=role,
            rate_limit=rate_limit,
            description=description,
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(db_key)
        await session.commit()
        
        print("\n" + "="*60)
        print("API Key Generated Successfully!")
        print("="*60)
        print(f"Username:    {username}")
        print(f"Role:        {role}")
        print(f"Rate Limit:  {rate_limit} requests/hour")
        print(f"API Key:     {api_key}")
        print("="*60)
        print("\nIMPORTANT: Save this API key securely. It will not be shown again.")
        print("\nUsage example:")
        print(f'curl -H "Authorization: Bearer {api_key}" \\')
        print('     -H "Content-Type: application/json" \\')
        print('     -d \'{"model": "deepseek-coder:33b", "prompt": "Hello", "stream": false}\' \\')
        print('     http://your-server:8000/api/generate')
        print()

async def main():
    parser = argparse.ArgumentParser(description='Generate API key for Ollama API server')
    parser.add_argument('username', help='Username for the API key')
    parser.add_argument('--role', choices=['admin', 'user', 'readonly'], 
                       default='user', help='User role (default: user)')
    parser.add_argument('--rate-limit', type=int, default=1000,
                       help='Rate limit per hour (default: 1000)')
    parser.add_argument('--description', help='Description for this API key')
    
    args = parser.parse_args()
    
    await create_api_key(
        username=args.username,
        role=args.role,
        rate_limit=args.rate_limit,
        description=args.description
    )

if __name__ == "__main__":
    asyncio.run(main())
