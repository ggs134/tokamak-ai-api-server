# Docker 사용 가이드

> **참고**: Docker 없이도 사용할 수 있습니다! Python만으로 바로 실행할 수 있습니다. Docker는 프로덕션 배포나 환경 일관성이 필요할 때 사용하세요.

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [빠른 시작](#빠른-시작)
3. [환경 변수 설정](#환경-변수-설정)
4. [시크릿 키 설정](#시크릿-키-설정-방법)
5. [데이터베이스 초기화](#데이터베이스-초기화)
6. [유저(API 키) 관리](#docker-환경에서-유저api-키-추가하기)
7. [유용한 명령어](#유용한-docker-명령어)
8. [문제 해결](#문제-해결)

## 사전 요구사항

- Docker 20.10 이상
- Docker Compose 2.0 이상 (또는 Docker Desktop에 포함된 `docker compose`)

## 빠른 시작

```bash
# 필요한 디렉토리 생성
mkdir -p logs data

# Docker 이미지 빌드 및 서버 시작
docker compose up -d --build

# 서버 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f tokamak-ai-api

# 헬스체크 확인
curl http://localhost:8000/health
```

## Docker Compose로 실행

### 개발 모드 (Nginx 없음)

```bash
# API 서버만 실행 (포트 8000 직접 접근)
docker compose up -d

# 빌드와 함께 실행
docker compose up -d --build

# 직접 접근
curl http://localhost:8000/health

# Swagger UI 접근
# 브라우저에서 http://localhost:8000/docs 열기
```

### 프로덕션 모드 (Nginx 포함)

```bash
# nginx 리버스 프록시와 함께 시작
docker compose --profile production up -d

# nginx를 통해 접근 (포트 80)
curl http://localhost/health

# 또는 커스텀 포트 지정
NGINX_HTTP_PORT=8080 docker compose --profile production up -d
```

## 환경 변수 설정

Docker Compose는 자동으로 프로젝트 루트 디렉토리의 `.env` 파일을 읽어서 환경 변수로 사용합니다.

### 방법 1: .env 파일 생성 (권장)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하세요:

```bash
# .env 파일 생성
cat > .env << 'EOF'
# API 포트 설정
API_PORT=8000                    # 직접 API 포트 (개발 모드)
NGINX_HTTP_PORT=80               # Nginx HTTP 포트 (프로덕션)
NGINX_HTTPS_PORT=443             # Nginx HTTPS 포트 (프로덕션)

# Ollama 서버 설정
# Docker 컨테이너에서 호스트 머신의 Ollama에 접근하려면 host.docker.internal 사용
OLLAMA_SERVERS=http://host.docker.internal:11434

# 여러 Ollama 서버를 사용하는 경우 (쉼표로 구분)
# OLLAMA_SERVERS=http://192.168.1.101:11434,http://192.168.1.102:11434,http://192.168.1.103:11434

# 보안 - 반드시 변경하세요!
# 강력한 시크릿 키 생성: openssl rand -hex 32
SECRET_KEY=change-this-secret-key-to-a-strong-random-value

# 속도 제한 설정
DEFAULT_RATE_LIMIT=1000          # 기본 시간당 요청 수
RATE_LIMIT_WINDOW=3600           # 윈도우 시간(초) - 1시간

# 로깅 레벨
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR

# 워커 수 (동시 처리 수)
WORKERS=4                         # CPU 코어 수에 맞게 조정

# 모니터링 (선택사항)
ENABLE_METRICS=true
METRICS_PORT=9090
EOF
```

또는 텍스트 에디터로 직접 생성:

```bash
nano .env
# 또는
vim .env
# 또는
code .env  # VS Code 사용 시
```

### 방법 2: 환경 변수로 직접 설정

`.env` 파일 없이 명령줄에서 직접 설정:

```bash
# 환경 변수를 직접 지정하여 실행
OLLAMA_SERVERS=http://192.168.1.101:11434 \
SECRET_KEY=$(openssl rand -hex 32) \
docker compose up -d
```

### 방법 3: 기본값 사용

`.env` 파일이 없어도 `docker-compose.yml`에 기본값이 설정되어 있어서 바로 실행할 수 있습니다:

```bash
# .env 파일 없이 실행 (기본값 사용)
docker compose up -d
```

기본값:
- `API_PORT=8000`
- `OLLAMA_SERVERS=http://host.docker.internal:11434`
- `SECRET_KEY=change-this-secret-key`
- `DEFAULT_RATE_LIMIT=1000`
- `RATE_LIMIT_WINDOW=3600`
- `LOG_LEVEL=INFO`
- `WORKERS=4`

### .env 파일 예제

```env
# ============================================
# API 서버 포트 설정
# ============================================
API_PORT=8000
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443

# ============================================
# Ollama 백엔드 서버 설정
# ============================================
# 단일 서버
OLLAMA_SERVERS=http://host.docker.internal:11434

# 여러 서버 (로드 밸런싱)
# OLLAMA_SERVERS=http://192.168.1.101:11434,http://192.168.1.102:11434,http://192.168.1.103:11434

# ============================================
# 보안 설정
# ============================================
# 강력한 시크릿 키 생성 방법:
# openssl rand -hex 32
SECRET_KEY=your-very-strong-secret-key-here-minimum-32-characters

# ============================================
# 속도 제한 설정
# ============================================
DEFAULT_RATE_LIMIT=1000          # 시간당 최대 요청 수
RATE_LIMIT_WINDOW=3600           # 시간 윈도우 (초)

# ============================================
# 로깅 설정
# ============================================
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR

# ============================================
# 성능 설정
# ============================================
WORKERS=4                         # 동시 워커 수 (CPU 코어 수에 맞게 조정)

# ============================================
# 모니터링 설정 (선택사항)
# ============================================
ENABLE_METRICS=true
METRICS_PORT=9090
```

### .env 파일 업데이트 방법

Docker 환경에서 `.env` 파일을 업데이트하는 방법:

**1단계: .env 파일 편집**

```bash
# 프로젝트 루트 디렉토리에서
nano .env
# 또는
vim .env
# 또는
code .env  # VS Code 사용 시
```

**2단계: 변경사항 적용**

`.env` 파일을 변경한 후에는 **컨테이너를 재시작**해야 변경사항이 적용됩니다:

```bash
# 방법 1: 컨테이너 재시작 (권장)
docker compose down
docker compose up -d

# 방법 2: 컨테이너만 재시작 (네트워크 유지)
docker compose restart tokamak-ai-api

# 방법 3: 완전히 재빌드 (코드 변경도 포함)
docker compose down
docker compose up -d --build
```

**3단계: 변경사항 확인**

```bash
# Docker Compose가 읽는 환경 변수 확인
docker compose config | grep -A 20 "environment:"

# 컨테이너 내부의 실제 환경 변수 확인
docker compose exec tokamak-ai-api env | grep -E "(OLLAMA|SECRET|RATE|LOG|WORKER)"

# 특정 변수만 확인
docker compose exec tokamak-ai-api env | grep OLLAMA_SERVERS
docker compose exec tokamak-ai-api env | grep SECRET_KEY
```

**주의사항:**

⚠️ **중요**: `.env` 파일을 변경한 후에는 반드시 컨테이너를 재시작해야 합니다. Docker Compose는 컨테이너 시작 시에만 `.env` 파일을 읽습니다.

**자주 업데이트하는 설정들:**

```bash
# Ollama 서버 주소 변경
# .env 파일에서:
OLLAMA_SERVERS=http://192.168.1.101:11434,http://192.168.1.102:11434

# 적용
docker compose restart tokamak-ai-api

# 로그 레벨 변경
# .env 파일에서:
LOG_LEVEL=DEBUG

# 적용
docker compose restart tokamak-ai-api

# 워커 수 변경
# .env 파일에서:
WORKERS=8

# 적용
docker compose restart tokamak-ai-api
```

**빠른 업데이트 예제:**

```bash
# 1. .env 파일 편집
nano .env

# 2. 변경사항 확인
cat .env | grep OLLAMA_SERVERS

# 3. 컨테이너 재시작
docker compose restart tokamak-ai-api

# 4. 로그 확인 (정상 작동 확인)
docker compose logs -f tokamak-ai-api
```

### .env 파일 확인

설정한 환경 변수가 제대로 적용되었는지 확인:

```bash
# Docker Compose가 읽는 환경 변수 확인
docker compose config

# 특정 서비스의 환경 변수 확인
docker compose exec tokamak-ai-api env | grep -E "(OLLAMA|SECRET|RATE|LOG|WORKER)"
```

## 시크릿 키 설정 방법

### 방법 1: .env 파일에 추가 (가장 권장)

**1단계: 강력한 시크릿 키 생성**

```bash
# 방법 A: openssl 사용
openssl rand -hex 32

# 방법 B: Python 사용
python -c "import secrets; print(secrets.token_hex(32))"

# 방법 C: Node.js 사용 (있는 경우)
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

**2단계: .env 파일에 추가**

```bash
# .env 파일이 없으면 생성
nano .env

# 또는 기존 .env 파일 편집
nano .env
```

`.env` 파일에 다음 줄 추가:

```env
SECRET_KEY=생성한-시크릿-키-여기에-붙여넣기
```

예시:
```env
SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0
```

**3단계: 적용**

```bash
# 컨테이너 재시작
docker compose down
docker compose up -d
```

### 방법 2: 명령줄에서 직접 설정

`.env` 파일 없이 실행 시:

```bash
# 시크릿 키를 생성하고 바로 사용
SECRET_KEY=$(openssl rand -hex 32) docker compose up -d
```

또는 이미 실행 중인 컨테이너에 적용:

```bash
# 컨테이너 중지
docker compose down

# 새 시크릿 키로 시작
SECRET_KEY=$(openssl rand -hex 32) docker compose up -d
```

### 방법 3: 환경 변수 파일 사용 (프로덕션 권장)

별도의 시크릿 파일을 만들어 사용:

```bash
# 시크릿 파일 생성 (권한 제한)
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env.secret
chmod 600 .env.secret  # 소유자만 읽기/쓰기 가능

# docker-compose.yml에서 사용하려면 env_file 추가 필요
# 또는 수동으로 로드
source .env.secret
docker compose up -d
```

### 방법 4: Docker Secrets 사용 (Docker Swarm 모드)

프로덕션 환경에서 더 안전한 방법:

```bash
# Docker Swarm 초기화 (아직 안 했다면)
docker swarm init

# 시크릿 생성
echo "your-secret-key-here" | docker secret create secret_key -

# docker-compose.yml에 secrets 섹션 추가 필요
```

### 시크릿 키 확인 방법

설정한 시크릿 키가 제대로 적용되었는지 확인:

```bash
# 방법 1: Docker Compose 설정 확인
docker compose config | grep SECRET_KEY

# 방법 2: 컨테이너 내부 환경 변수 확인
docker compose exec tokamak-ai-api env | grep SECRET_KEY

# 방법 3: 실행 중인 컨테이너 환경 변수 확인
docker inspect tokamak-ai-api-server | grep -A 10 "Env"
```

### 시크릿 키 변경 시 주의사항

⚠️ **중요**: 시크릿 키를 변경하면 기존에 발급된 JWT 토큰이 무효화될 수 있습니다. 사용 중인 시스템에서는 신중하게 변경하세요.

```bash
# 1. 기존 컨테이너 중지
docker compose down

# 2. .env 파일에서 SECRET_KEY 변경
nano .env

# 3. 새 컨테이너 시작
docker compose up -d

# 4. 확인
docker compose logs tokamak-ai-api | grep -i secret
```

### 보안 모범 사례

1. **강력한 키 사용**: 최소 32자 이상의 랜덤 문자열
2. **Git에 커밋 금지**: `.env` 파일은 절대 Git에 커밋하지 마세요
3. **파일 권한 제한**: `.env` 파일 권한을 600으로 설정
   ```bash
   chmod 600 .env
   ```
4. **정기적 순환**: 프로덕션에서는 주기적으로 시크릿 키 교체
5. **환경별 분리**: 개발/스테이징/프로덕션 환경마다 다른 키 사용

### 중요 사항

1. **.env 파일은 Git에 커밋하지 마세요!**
   - `.gitignore`에 `.env`가 포함되어 있는지 확인
   - 민감한 정보(시크릿 키 등)가 포함되어 있습니다

2. **프로덕션 환경에서는 반드시 SECRET_KEY 변경**
   ```bash
   # 강력한 시크릿 키 생성
   openssl rand -hex 32
   ```

3. **Ollama 서버 주소 확인**
   - macOS/Windows: `host.docker.internal` 사용 가능
   - Linux: 실제 IP 주소 사용 또는 `extra_hosts` 설정 확인

4. **환경 변수 변경 후 재시작 필요**
   ```bash
   docker compose down
   docker compose up -d
   ```

## 데이터베이스 초기화

Docker 컨테이너 내에서 데이터베이스를 초기화하려면:

```bash
# 컨테이너 내부에서 실행
docker compose exec tokamak-ai-api python scripts/init_db.py

# 또는 호스트에서 직접 실행 (로컬 Python 환경 필요)
python scripts/init_db.py
```

**참고**: 데이터베이스 파일은 `./data` 디렉토리에 저장되며, Docker 볼륨으로 마운트됩니다.

## Docker 환경에서 유저(API 키) 추가하기

Docker 환경에서 새로운 유저를 추가하는 방법은 3가지가 있습니다:

### 방법 1: 스크립트 사용 (권장)

컨테이너 내부에서 `generate_api_key.py` 스크립트를 실행합니다:

```bash
# 기본 사용자 생성 (role: user, rate_limit: 1000)
docker compose exec tokamak-ai-api python scripts/generate_api_key.py kevin

# 관리자 권한으로 생성
docker compose exec tokamak-ai-api python scripts/generate_api_key.py admin_user --role admin --rate-limit 10000

# 설명과 함께 생성
docker compose exec tokamak-ai-api python scripts/generate_api_key.py developer1 \
  --role user \
  --rate-limit 1000 \
  --description "프론트엔드 개발자"
```

**스크립트 옵션:**
- `username` (필수): 사용자 이름
- `--role`: `admin`, `user`, `readonly` (기본값: `user`)
- `--rate-limit`: 시간당 요청 제한 (기본값: 1000)
- `--description`: 설명 (선택사항)

**예시 출력:**
```
============================================================
API Key Generated Successfully!
============================================================
Username:    kevin
Role:        user
Rate Limit:  1000 requests/hour
API Key:     sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
============================================================

IMPORTANT: Save this API key securely. It will not be shown again.
```

### 방법 2: API 엔드포인트 사용

관리자 API 키가 있는 경우, REST API를 통해 유저를 추가할 수 있습니다:

```bash
# 관리자 API 키로 새 유저 생성
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer1",
    "role": "user",
    "rate_limit": 1000,
    "description": "프론트엔드 개발자"
  }'
```

**응답 예시:**
```json
{
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "username": "developer1",
  "role": "user",
  "rate_limit": 1000,
  "created_at": "2025-12-17T04:30:00.000000Z",
  "description": "프론트엔드 개발자"
}
```

### 방법 3: 호스트에서 직접 실행

로컬에 Python 환경이 있다면 호스트에서 직접 실행할 수 있습니다:

```bash
# 가상 환경 활성화 (있는 경우)
source venv/bin/activate

# 스크립트 실행
python scripts/generate_api_key.py kevin --role user --rate-limit 1000
```

**주의**: 이 방법은 호스트의 Python 환경이 필요하며, 데이터베이스 경로가 올바르게 설정되어 있어야 합니다.

### 유저 관리 명령어

#### 모든 유저 목록 조회

```bash
# API 사용 (관리자 권한 필요)
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

#### 유저 삭제

```bash
# API 사용 (관리자 권한 필요)
curl -X DELETE http://localhost:8000/admin/api-keys/username \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

#### 초기 관리자 계정 생성

처음 서버를 시작할 때 기본 관리자 계정이 자동으로 생성됩니다:

```bash
# 데이터베이스 초기화 (관리자 계정 자동 생성)
docker compose exec tokamak-ai-api python scripts/init_db.py
```

이 명령은 다음을 수행합니다:
- 데이터베이스 테이블 생성
- 기본 관리자 계정 생성 (username: `admin`)
- 관리자 API 키 출력 (⚠️ 안전하게 저장하세요!)

### 실전 예제

**시나리오: 팀에 새 개발자 추가**

```bash
# 1. 컨테이너가 실행 중인지 확인
docker compose ps

# 2. 새 개발자 유저 생성
docker compose exec tokamak-ai-api python scripts/generate_api_key.py \
  alice \
  --role user \
  --rate-limit 2000 \
  --description "백엔드 개발자 - 프로젝트 A"

# 3. 생성된 API 키를 안전하게 전달
# (스크립트 출력에서 API 키를 복사하여 전달)

# 4. API 키 테스트
curl http://localhost:8000/auth/verify \
  -H "Authorization: Bearer sk-생성된-API-키"
```

**응답 예시:**
```json
{
  "valid": true,
  "username": "alice",
  "role": "user",
  "rate_limit": 2000,
  "is_active": true,
  "message": "API 키가 유효합니다."
}
```

## 유용한 Docker 명령어

```bash
# 서버 시작
docker compose up -d

# 서버 중지
docker compose down

# 서버 재시작
docker compose restart

# 로그 실시간 확인
docker compose logs -f tokamak-ai-api

# 최근 50줄 로그 확인
docker compose logs --tail=50 tokamak-ai-api

# 컨테이너 상태 확인
docker compose ps

# 컨테이너 내부 접속
docker compose exec tokamak-ai-api bash

# 이미지 재빌드 (코드 변경 후)
docker compose up -d --build

# 볼륨 및 네트워크까지 완전히 제거
docker compose down -v
```

## Docker 특징

- **보안**: non-root 사용자로 실행 (appuser)
- **헬스체크**: 자동 컨테이너 상태 모니터링
- **볼륨 마운트**: 데이터와 로그는 호스트에 저장
- **환경 변수**: `.env` 파일 또는 환경 변수로 설정 가능
- **자동 재시작**: 컨테이너가 중단되면 자동으로 재시작

## 문제 해결

### 컨테이너가 시작되지 않는 경우

```bash
# 로그 확인
docker compose logs tokamak-ai-api

# 컨테이너 상태 확인
docker compose ps

# 이미지 재빌드
docker compose build --no-cache
docker compose up -d
```

### 포트가 이미 사용 중인 경우

`.env` 파일에서 포트를 변경하거나, 사용 중인 프로세스를 종료하세요:

```bash
# 포트 사용 확인
lsof -i :8000

# 또는
docker compose down
# 다른 포트로 실행
API_PORT=8001 docker compose up -d
```

### Ollama 서버에 연결할 수 없는 경우

Docker 컨테이너에서 호스트의 Ollama에 접근하려면:
- macOS/Windows: `host.docker.internal` 사용 (자동 지원)
- Linux: `extra_hosts` 설정이 docker-compose.yml에 포함되어 있음

또는 Ollama 서버의 실제 IP 주소를 사용하세요.

## Nginx 추가 (프로덕션 권장 - 선택사항)

Nginx는 Docker Compose 프로파일을 사용하여 선택적 서비스로 포함되어 있습니다.

### Docker Compose 사용 (권장)

`docker-compose.yml`에는 `production` 프로파일로 nginx가 포함되어 있습니다:

```bash
# nginx와 함께 시작
docker compose --profile production up -d

# 중지
docker compose --profile production down

# 상태 확인
docker compose ps
```

### 수동 Nginx 설정

수동 설치의 경우 `config/nginx-config.conf`를 사용하세요:

```bash
# 설정 파일 복사
sudo cp config/nginx-config.conf /etc/nginx/sites-available/ollama-api
sudo ln -s /etc/nginx/sites-available/ollama-api /etc/nginx/sites-enabled/

# 테스트 및 재로드
sudo nginx -t
sudo systemctl reload nginx
```

**참고**: 환경에 맞게 `config/nginx-config.conf`의 `server_name`과 upstream 서버를 업데이트하세요.
