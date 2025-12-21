# 운영 서버 업데이트 가이드

운영 중인 서버를 안전하게 업데이트하는 방법을 안내합니다.

## 사전 준비

### 1. 백업 확인

업데이트 전에 다음을 백업하세요:

```bash
# 데이터베이스 백업
cp data/tokamak_ai_api.db data/tokamak_ai_api.db.backup.$(date +%Y%m%d_%H%M%S)

# 설정 파일 백업
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

### 2. 현재 버전 확인

```bash
# Git 커밋 확인
git log --oneline -5

# 또는 현재 코드 버전 확인
git describe --tags 2>/dev/null || git rev-parse --short HEAD
```

## 업데이트 방법

### 방법 1: Docker를 사용하는 경우 (권장)

#### 1단계: 코드 업데이트

```bash
# 운영 서버에 접속
ssh user@your-server

# 프로젝트 디렉토리로 이동
cd /path/to/api_server

# 최신 코드 가져오기
git fetch origin
git pull origin main

# 또는 특정 커밋으로 업데이트
git checkout 8d98ef2  # 최신 커밋 해시
```

#### 2단계: 데이터베이스 마이그레이션 (필요한 경우)

새로운 데이터베이스 스키마 변경사항이 있는 경우:

```bash
# 컨테이너 내에서 데이터베이스 마이그레이션 실행
docker compose exec tokamak-ai-api python -c "
import sqlite3

conn = sqlite3.connect('/app/data/tokamak_ai_api.db')
cursor = conn.cursor()

# 먼저 컬럼 존재 여부 확인 (더 안전한 방법)
cursor.execute('PRAGMA table_info(usage_logs)')
columns = [col[1] for col in cursor.fetchall()]

if 'prompt' not in columns:
    cursor.execute('ALTER TABLE usage_logs ADD COLUMN prompt TEXT')
    conn.commit()
    print('✓ prompt 컬럼 추가 완료')
else:
    print('✓ prompt 컬럼이 이미 존재합니다')

conn.close()
"
```

#### 3단계: Docker 이미지 재빌드 및 재시작

```bash
# 이미지 재빌드 (코드 변경사항 반영)
docker compose build tokamak-ai-api

# 서비스 재시작 (무중단 업데이트)
docker compose up -d --force-recreate tokamak-ai-api

# 또는 전체 재시작
docker compose down
docker compose up -d --build
```

#### 4단계: 상태 확인

```bash
# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f tokamak-ai-api

# 헬스 체크
curl http://localhost:8000/health

# API 엔드포인트 테스트
curl http://localhost:8000/admin/usage/testuser?days=1 \
  -H "Authorization: Bearer YOUR_ADMIN_KEY"
```

### 방법 2: systemd 서비스를 사용하는 경우

#### 1단계: 코드 업데이트

```bash
# 운영 서버에 접속
ssh user@your-server

# 프로젝트 디렉토리로 이동
cd /path/to/api_server

# 최신 코드 가져오기
git fetch origin
git pull origin main
```

#### 2단계: 업데이트 스크립트 실행

```bash
# 업데이트 스크립트 실행 (자동으로 백업, 업데이트, 재시작 수행)
./scripts/update.sh
```

또는 수동으로:

```bash
# 1. 서비스 중지
sudo systemctl stop tokamak-ai-api

# 2. 코드 복사 (프로젝트 루트에서)
cp -r app config docs scripts main.py requirements.txt /opt/tokamak-ai-api/

# 3. 의존성 업데이트
cd /opt/tokamak-ai-api
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 4. 데이터베이스 마이그레이션 (필요한 경우)
python -c "
import sqlite3
import os
import re

# .env 파일에서 DATABASE_URL 읽기 시도
db_path = None
env_paths = ['.env', '/opt/tokamak-ai-api/.env', os.path.join(os.getcwd(), '.env')]

for env_file in env_paths:
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        # sqlite+aiosqlite:///./tokamak_ai_api.db 또는 sqlite+aiosqlite:////app/data/tokamak_ai_api.db 형식 파싱
                        # 파일명도 동적으로 파싱
                        match = re.search(r'sqlite\+aiosqlite:///(.+?)/([^/]+\.db)', line)
                        if match:
                            path_part = match.group(1)
                            db_filename = match.group(2)
                            
                            # 상대 경로 처리 (./ 또는 //)
                            if path_part.startswith('./'):
                                path_part = path_part[2:]
                            elif path_part.startswith('//'):
                                path_part = path_part[1:]  # /app/data 형식
                            
                            # 경로 조합
                            if path_part:
                                db_path = os.path.join(path_part, db_filename)
                            else:
                                db_path = db_filename
                            
                            # 절대 경로가 아니면 .env 파일 기준으로 변환
                            if not os.path.isabs(db_path):
                                db_path = os.path.join(os.path.dirname(env_file), db_path)
                            
                            db_path = os.path.abspath(db_path)
                            break
        except Exception as e:
            pass

# .env에서 찾지 못한 경우 여러 가능한 경로 시도
if not db_path or not os.path.exists(db_path):
    possible_paths = [
        'tokamak_ai_api.db',  # 현재 디렉토리
        'data/tokamak_ai_api.db',  # data 서브디렉토리
        '/opt/tokamak-ai-api/tokamak_ai_api.db',  # 배포 경로
        '/opt/tokamak-ai-api/data/tokamak_ai_api.db',  # 배포 경로 (data)
        os.path.join(os.getcwd(), 'tokamak_ai_api.db'),  # 현재 작업 디렉토리
        os.path.join(os.getcwd(), 'data', 'tokamak_ai_api.db'),  # 현재 작업 디렉토리/data
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = os.path.abspath(path)
            break

if db_path and os.path.exists(db_path):
    print(f'데이터베이스 파일 발견: {db_path}')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 먼저 컬럼 존재 여부 확인 (더 안전한 방법)
    cursor.execute('PRAGMA table_info(usage_logs)')
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'prompt' not in columns:
        cursor.execute('ALTER TABLE usage_logs ADD COLUMN prompt TEXT')
        conn.commit()
        print('✓ prompt 컬럼 추가 완료')
    else:
        print('✓ prompt 컬럼이 이미 존재합니다')
    
    conn.close()
else:
    print('⚠ 데이터베이스 파일을 찾을 수 없습니다')
    print('\\n다음 방법을 시도해보세요:')
    print('1. .env 파일의 DATABASE_URL 확인')
    print('2. 데이터베이스 파일 위치 확인: find /opt -name tokamak_ai_api.db 2>/dev/null')
    print('3. 수동으로 경로 지정: python -c \"import sqlite3; conn=sqlite3.connect(\\\"/path/to/tokamak_ai_api.db\\\"); ...\"')
"

# 5. 서비스 재시작
sudo systemctl start tokamak-ai-api
sudo systemctl status tokamak-ai-api
```

## 주요 변경사항 (최신 업데이트)

### 데이터베이스 변경사항

- `usage_logs` 테이블에 `prompt` 컬럼 추가
- 기존 데이터는 `prompt`가 `NULL`로 유지됨 (새 요청부터 저장)

### API 변경사항

- `/admin/usage/{username}` 엔드포인트 개선:
  - `limit` 파라미터 추가 (최근 요청 개수 제한)
  - `recent_requests` 배열 추가 (프롬프트 내용 포함)
  - 파라미터 검증 강화

## 롤백 방법

문제가 발생하면 이전 버전으로 롤백:

### Docker 방식

```bash
# 이전 커밋으로 체크아웃
git checkout <previous-commit-hash>

# 이미지 재빌드 및 재시작
docker compose build tokamak-ai-api
docker compose up -d --force-recreate tokamak-ai-api
```

### systemd 방식

```bash
# 이전 커밋으로 체크아웃
git checkout <previous-commit-hash>

# 업데이트 스크립트 재실행
./scripts/update.sh
```

## 무중단 업데이트 (고급)

### Blue-Green 배포

```bash
# 1. 새 컨테이너 빌드
docker compose -f docker-compose.yml -f docker-compose.blue.yml build

# 2. 새 컨테이너 시작 (다른 포트)
docker compose -f docker-compose.yml -f docker-compose.blue.yml up -d

# 3. 헬스 체크 확인
curl http://localhost:8001/health

# 4. 트래픽 전환 (Nginx 설정 변경)
# nginx 설정에서 upstream을 새 포트로 변경

# 5. 구 컨테이너 중지
docker compose down
```

## 문제 해결

### 업데이트 후 서비스가 시작되지 않는 경우

```bash
# 로그 확인
docker compose logs tokamak-ai-api
# 또는
sudo journalctl -u tokamak-ai-api -n 100

# 데이터베이스 확인
docker compose exec tokamak-ai-api python -c "
import sqlite3
import os

db_path = '/app/data/tokamak_ai_api.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM usage_logs')
    count = cursor.fetchone()[0]
    print(f'Database connection OK (usage_logs: {count} records)')
    conn.close()
else:
    print('Database file not found')
"
```

### 데이터베이스 마이그레이션 오류

```bash
# 수동으로 컬럼 추가
docker compose exec tokamak-ai-api python -c "
import sqlite3

conn = sqlite3.connect('/app/data/tokamak_ai_api.db')
cursor = conn.cursor()

# 먼저 컬럼 존재 여부 확인
cursor.execute('PRAGMA table_info(usage_logs)')
columns = [col[1] for col in cursor.fetchall()]

if 'prompt' not in columns:
    cursor.execute('ALTER TABLE usage_logs ADD COLUMN prompt TEXT')
    conn.commit()
    print('✓ prompt 컬럼 추가 완료')
else:
    print('✓ prompt 컬럼이 이미 존재합니다')

conn.close()
"
```

## 체크리스트

업데이트 전:
- [ ] 데이터베이스 백업
- [ ] 설정 파일 백업
- [ ] 현재 버전 확인
- [ ] 업데이트 내용 확인

업데이트 중:
- [ ] 코드 업데이트
- [ ] 데이터베이스 마이그레이션 (필요한 경우)
- [ ] 의존성 업데이트
- [ ] 서비스 재시작

업데이트 후:
- [ ] 서비스 상태 확인
- [ ] 헬스 체크 확인
- [ ] API 엔드포인트 테스트
- [ ] 로그 확인 (에러 없음)
- [ ] 기능 테스트

## 참고

- 업데이트는 **비피크 시간**에 수행하는 것을 권장합니다
- 중요한 업데이트는 **스테이징 환경**에서 먼저 테스트하세요
- 데이터베이스 변경사항이 있는 경우 **반드시 백업**하세요

