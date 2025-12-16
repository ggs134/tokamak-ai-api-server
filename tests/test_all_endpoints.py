#!/usr/bin/env python3
"""
전체 API 엔드포인트 테스트 스크립트
"""
import asyncio
import sys
import json
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import AsyncSessionLocal, APIKey
from sqlalchemy import select
from app.auth import hash_api_key, verify_api_key
from fastapi.security import HTTPAuthorizationCredentials
from fastapi import HTTPException

async def get_admin_api_key():
    """Admin API 키를 데이터베이스에서 찾아서 해시로 검증"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(APIKey).where(
                APIKey.role == 'admin',
                APIKey.is_active == True
            )
        )
        admin_key = result.scalar_one_or_none()
        if admin_key:
            print(f"✓ Admin 키 발견: {admin_key.username}")
            await db.close()
            await db.bind.dispose()
            return admin_key
        else:
            print("✗ Admin 키를 찾을 수 없습니다.")
            await db.close()
            await db.bind.dispose()
            return None

async def test_api_key(api_key_hash, test_key):
    """API 키가 맞는지 테스트"""
    from app.auth import hash_api_key
    test_hash = hash_api_key(test_key)
    return test_hash == api_key_hash

async def main():
    print("=" * 60)
    print("API 엔드포인트 전체 테스트")
    print("=" * 60)
    
    # Admin 키 찾기
    admin_key_record = await get_admin_api_key()
    if not admin_key_record:
        print("\n❌ Admin 키가 없어 테스트를 진행할 수 없습니다.")
        print("먼저 admin 키를 생성해주세요.")
        return
    
    # 알려진 API 키들로 테스트
    known_keys = [
        "sk-8ig-52kmrs0Kup-1u1-zsJU2zZJlkb8G7VArSulvqKI",
    ]
    
    admin_api_key = None
    for key in known_keys:
        test_hash = hash_api_key(key)
        if test_hash == admin_key_record.api_key_hash:
            admin_api_key = key
            print(f"✓ Admin API 키 확인됨")
            break
    
    if not admin_api_key:
        print("\n⚠️  알려진 API 키로 admin 키를 찾을 수 없습니다.")
        print("API 키를 직접 입력하거나 새로 생성해야 합니다.")
        print("\n테스트를 계속하려면 API 키를 입력하세요 (또는 Enter로 건너뛰기):")
        user_input = input("API Key: ").strip()
        if user_input:
            admin_api_key = user_input
        else:
            print("테스트를 중단합니다.")
            return
    
    print(f"\n사용할 Admin API Key: {admin_api_key[:20]}...")
    print("\n" + "=" * 60)
    print("테스트 시작")
    print("=" * 60)
    
    import httpx
    base_url = "http://localhost:8000"
    headers = {
        "Authorization": f"Bearer {admin_api_key}",
        "Content-Type": "application/json"
    }
    
    # 1. Health Check
    print("\n[1] GET /health")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health check 성공")
            data = response.json()
            print(f"  - Status: {data.get('status')}")
            print(f"  - Database: {data.get('database_connected')}")
            print(f"  - Ollama servers: {len(data.get('ollama_servers', []))}개")
        else:
            print(f"✗ Health check 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ Health check 오류: {e}")
    
    # 2. List Models (인증 불필요)
    print("\n[2] GET /api/tags")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url}/api/tags")
        if response.status_code == 200:
            print("✓ 모델 목록 조회 성공")
            data = response.json()
            models = data.get('models', [])
            print(f"  - 모델 개수: {len(models)}개")
            if models:
                print(f"  - 첫 번째 모델: {models[0].get('name', 'N/A')}")
        else:
            print(f"✗ 모델 목록 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ 모델 목록 조회 오류: {e}")
    
    # 3. Generate (non-streaming)
    print("\n[3] POST /api/generate (non-streaming)")
    try:
        payload = {
            "model": "gpt-oss:20b",
            "prompt": "Hello, world!",
            "stream": False
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/api/generate",
                headers=headers,
                json=payload
            )
        if response.status_code == 200:
            print("✓ Generate 요청 성공")
            data = response.json()
            print(f"  - 응답 길이: {len(data.get('response', ''))} 문자")
            print(f"  - Done: {data.get('done', False)}")
        else:
            print(f"✗ Generate 요청 실패: {response.status_code}")
            print(f"  - 응답: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Generate 요청 오류: {e}")
    
    # 4. Chat
    print("\n[4] POST /api/chat")
    try:
        payload = {
            "model": "gpt-oss:20b",
            "messages": [
                {"role": "user", "content": "안녕하세요!"}
            ],
            "stream": False
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/api/chat",
                headers=headers,
                json=payload
            )
        if response.status_code == 200:
            print("✓ Chat 요청 성공")
            data = response.json()
            print(f"  - 응답 메시지: {data.get('message', {}).get('content', '')[:50]}...")
        else:
            print(f"✗ Chat 요청 실패: {response.status_code}")
            print(f"  - 응답: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Chat 요청 오류: {e}")
    
    # 5. Embeddings (엔드포인트 없음 - 스킵)
    print("\n[5] POST /api/embeddings")
    print("⚠️  Embeddings 엔드포인트가 구현되지 않았습니다 (스킵)")
    
    # 6. My Usage
    print("\n[6] GET /usage/me")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{base_url}/usage/me",
                headers=headers
            )
        if response.status_code == 200:
            print("✓ 사용량 조회 성공")
            data = response.json()
            print(f"  - Username: {data.get('username')}")
            print(f"  - Rate limit: {data.get('rate_limit')}")
            print(f"  - Current usage: {data.get('current_hour_usage')}")
            print(f"  - Remaining: {data.get('remaining')}")
        else:
            print(f"✗ 사용량 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ 사용량 조회 오류: {e}")
    
    # 7. List API Keys (Admin)
    print("\n[7] GET /admin/api-keys")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{base_url}/admin/api-keys",
                headers=headers
            )
        if response.status_code == 200:
            print("✓ API 키 목록 조회 성공")
            data = response.json()
            keys = data.get('keys', [])
            print(f"  - 등록된 키 개수: {len(keys)}개")
            for key in keys[:3]:
                print(f"    - {key.get('username')} ({key.get('role')})")
        else:
            print(f"✗ API 키 목록 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ API 키 목록 조회 오류: {e}")
    
    # 8. Create API Key (Admin)
    print("\n[8] POST /admin/api-keys (새 키 생성)")
    try:
        import random
        test_username = f"testuser_{random.randint(1000, 9999)}"
        payload = {
            "username": test_username,
            "role": "user",
            "rate_limit": 500,
            "description": "테스트용 API 키"
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{base_url}/admin/api-keys",
                headers=headers,
                json=payload
            )
        if response.status_code == 200:
            print("✓ API 키 생성 성공")
            data = response.json()
            new_key = data.get('api_key', '')
            print(f"  - Username: {data.get('username')}")
            print(f"  - Role: {data.get('role')}")
            print(f"  - API Key: {new_key[:30]}...")
            
            # 생성된 키로 테스트
            print("\n[8-1] 생성된 키로 Generate 테스트")
            test_headers = {
                "Authorization": f"Bearer {new_key}",
                "Content-Type": "application/json"
            }
            test_payload = {
                "model": "gpt-oss:20b",
                "prompt": "test",
                "stream": False
            }
            with httpx.Client(timeout=30.0) as client:
                test_response = client.post(
                    f"{base_url}/api/generate",
                    headers=test_headers,
                    json=test_payload
                )
            if test_response.status_code == 200:
                print("✓ 생성된 키로 요청 성공")
            else:
                print(f"✗ 생성된 키로 요청 실패: {test_response.status_code}")
        else:
            print(f"✗ API 키 생성 실패: {response.status_code}")
            print(f"  - 응답: {response.text[:200]}")
    except Exception as e:
        print(f"✗ API 키 생성 오류: {e}")
    
    # 9. Admin Usage
    print("\n[9] GET /admin/usage/{username}")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{base_url}/admin/usage/admin_new",
                headers=headers,
                params={"days": 1}
            )
        if response.status_code == 200:
            print("✓ Admin 사용량 조회 성공")
            data = response.json()
            print(f"  - 총 요청 수: {data.get('total_requests', 0)}")
            print(f"  - 총 토큰: {data.get('total_tokens', 0)}")
        else:
            print(f"✗ Admin 사용량 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ Admin 사용량 조회 오류: {e}")
    
    # 10. OpenAPI Schema
    print("\n[10] GET /openapi.json")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base_url}/openapi.json")
        if response.status_code == 200:
            print("✓ OpenAPI 스키마 조회 성공")
            data = response.json()
            paths = data.get('paths', {})
            print(f"  - 엔드포인트 개수: {len(paths)}개")
        else:
            print(f"✗ OpenAPI 스키마 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"✗ OpenAPI 스키마 조회 오류: {e}")
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

