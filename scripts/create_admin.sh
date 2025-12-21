#!/bin/bash

# Tokamak AI API Server - Admin 사용자 생성 스크립트
# 데이터베이스에 직접 admin 사용자를 생성합니다

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Admin 사용자 생성                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# 사용자 입력 받기
if [ -z "$1" ]; then
    read -p "사용자 이름 (기본값: admin): " USERNAME
    USERNAME=${USERNAME:-admin}
else
    USERNAME="$1"
fi

read -p "Rate Limit (기본값: 10000): " RATE_LIMIT
RATE_LIMIT=${RATE_LIMIT:-10000}

read -p "설명 (선택사항): " DESCRIPTION

# Python 스크립트 실행 (쉘 변수를 환경 변수로 전달)
export CREATE_ADMIN_USERNAME="$USERNAME"
export CREATE_ADMIN_RATE_LIMIT="$RATE_LIMIT"
export CREATE_ADMIN_DESCRIPTION="$DESCRIPTION"

python3 << 'PYTHON_SCRIPT'
import sqlite3
import os
import re
import secrets
import hashlib
from datetime import datetime, timezone

# 쉘 변수에서 값 가져오기
username = os.environ.get('CREATE_ADMIN_USERNAME', 'admin')
rate_limit = int(os.environ.get('CREATE_ADMIN_RATE_LIMIT', '10000'))
description = os.environ.get('CREATE_ADMIN_DESCRIPTION', '')

# 데이터베이스 경로 찾기
db_path = None

# 환경 변수에서 직접 경로 지정된 경우
if 'DB_PATH' in os.environ:
    db_path = os.environ['DB_PATH']
    if not os.path.exists(db_path):
        print(f"\n✗ 오류: 지정된 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        exit(1)

# .env 파일에서 DATABASE_URL 읽기 시도
if not db_path:
    env_paths = ['.env', '/opt/tokamak-ai-api/.env', os.path.join(os.getcwd(), '.env')]
    
    for env_file in env_paths:
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('DATABASE_URL='):
                            match = re.search(r'sqlite\+aiosqlite:///(.+?)/([^/]+\.db)', line)
                            if match:
                                path_part = match.group(1)
                                db_filename = match.group(2)
                                
                                if path_part.startswith('./'):
                                    path_part = path_part[2:]
                                elif path_part.startswith('//'):
                                    path_part = path_part[1:]
                                
                                if path_part:
                                    db_path = os.path.join(path_part, db_filename)
                                else:
                                    db_path = db_filename
                                
                                if not os.path.isabs(db_path):
                                    db_path = os.path.join(os.path.dirname(env_file), db_path)
                                
                                db_path = os.path.abspath(db_path)
                                break
            except Exception:
                pass

# .env에서 찾지 못한 경우 여러 가능한 경로 시도
if not db_path or not os.path.exists(db_path):
    possible_paths = [
        'tokamak_ai_api.db',
        'data/tokamak_ai_api.db',
        '/opt/tokamak-ai-api/tokamak_ai_api.db',
        '/opt/tokamak-ai-api/data/tokamak_ai_api.db',
        os.path.join(os.getcwd(), 'tokamak_ai_api.db'),
        os.path.join(os.getcwd(), 'data', 'tokamak_ai_api.db'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = os.path.abspath(path)
            break

if not db_path or not os.path.exists(db_path):
    print("\n✗ 오류: 데이터베이스 파일을 찾을 수 없습니다")
    print("\n시도한 경로:")
    for path in possible_paths:
        print(f"  - {path}")
    print("\n데이터베이스 파일 경로를 직접 지정하세요:")
    print("  DB_PATH=/path/to/tokamak_ai_api.db ./scripts/create_admin.sh")
    exit(1)

print(f"✓ 데이터베이스 파일 발견: {db_path}")

# 데이터베이스 연결
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 사용자 이름 중복 확인
cursor.execute('SELECT username FROM api_keys WHERE username = ?', (username,))
existing = cursor.fetchone()

if existing:
    print(f"\n⚠ 경고: 사용자 이름 '{username}'이 이미 존재합니다")
    response = input("기존 사용자를 덮어쓰시겠습니까? (y/n): ")
    if response.lower() != 'y':
        print("취소되었습니다.")
        conn.close()
        exit(0)
    
    # 기존 사용자 삭제
    cursor.execute('DELETE FROM api_keys WHERE username = ?', (username,))
    print(f"기존 사용자 삭제됨")

# API 키 생성
random_part = secrets.token_urlsafe(32)
api_key = f"sk-{random_part}"
api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

# 현재 시간
now = datetime.now(timezone.utc).isoformat()

# 데이터베이스에 삽입
try:
    cursor.execute('''
        INSERT INTO api_keys 
        (api_key_hash, username, role, rate_limit, is_active, description, created_at)
        VALUES (?, ?, 'admin', ?, 1, ?, ?)
    ''', (api_key_hash, username, rate_limit, description if description else None, now))
    
    conn.commit()
    
    print("\n" + "="*60)
    print("Admin 사용자 생성 완료!")
    print("="*60)
    print(f"사용자 이름:    {username}")
    print(f"역할:          admin")
    print(f"Rate Limit:    {rate_limit} requests/hour")
    if description:
        print(f"설명:          {description}")
    print(f"\nAPI Key:     {api_key}")
    print("="*60)
    print("\n⚠️  중요: 이 API 키를 안전하게 저장하세요!")
    print("     이 키는 다시 표시되지 않습니다.")
    print("="*60)
    print("")
    print("사용 예시:")
    print(f'curl -H "Authorization: Bearer {api_key}" \\')
    print('     http://localhost:8000/health')
    print("")
    
except sqlite3.IntegrityError as e:
    print(f"\n✗ 오류: {e}")
    print("API 키 해시가 중복되었습니다. 다시 시도하세요.")
    conn.rollback()
    exit(1)
except Exception as e:
    print(f"\n✗ 오류: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()
PYTHON_SCRIPT

