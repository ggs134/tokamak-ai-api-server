# Tokamak AI API Server

팀 협업을 위한 엔터프라이즈급 인증 및 로드 밸런싱 AI API 서버입니다.

## 주요 기능

- 🔐 **인증**: 역할 기반 접근 제어를 지원하는 API 키 기반 인증
- ⚖️ **로드 밸런싱**: 자동 장애 조치 및 최소 연결 수 기반 로드 밸런싱
- 🚦 **속도 제한**: SQLite 기반 사용자별 속도 제한
- 📊 **사용량 추적**: 상세한 사용량 통계 및 로깅
- 🏥 **헬스 체크**: 자동 백엔드 헬스 모니터링
- 🔄 **스트리밍 지원**: 스트리밍 응답 완전 지원
- 📈 **관리자 대시보드**: 사용량 분석 및 API 키 관리

## 아키텍처

```
Client → FastAPI Server → Load Balancer → Ollama Backend 1
                                        → Ollama Backend 2
                                        → Ollama Backend 3
           ↓
        SQLite (Rate Limiting, Usage Logs & API Keys)
```

## 프로젝트 구조

```
api_server/
├── app/                    # 애플리케이션 핵심 코드
│   ├── auth.py            # 인증 및 권한 관리
│   ├── config.py          # 설정 관리
│   ├── database.py        # 데이터베이스 모델 및 연결
│   ├── load_balancer.py   # 로드 밸런싱 로직
│   ├── models.py          # Pydantic 모델
│   ├── monitoring.py      # 모니터링 및 헬스 체크
│   └── rate_limiter.py    # 속도 제한 구현
├── config/                 # 설정 파일
│   └── nginx-config.conf  # Nginx 리버스 프록시 설정
├── docs/                   # 문서
│   ├── API.md            # API 엔드포인트 문서
│   ├── ARCHITECTURE.md   # 아키텍처 문서
│   ├── DOCKER.md         # Docker 사용 가이드
│   ├── INSTALL.md        # 설치 가이드
│   ├── NETWORK_OPTIMIZATION.md  # 네트워크 최적화
│   └── QUICKSTART.md     # 빠른 시작 가이드
├── scripts/                # 유틸리티 스크립트
│   ├── deploy.sh         # 배포 스크립트
│   ├── generate_api_key.py  # API 키 생성
│   ├── init_db.py        # 데이터베이스 초기화
│   └── run.sh            # 서버 시작 스크립트
├── tests/                  # 테스트 파일
│   ├── test_all_endpoints.py  # 전체 엔드포인트 테스트
│   └── test_client.py     # 예제 클라이언트
├── main.py                 # 애플리케이션 진입점
├── requirements.txt        # Python 의존성
├── Dockerfile             # Docker 이미지 빌드
├── docker-compose.yml     # Docker Compose 설정
└── README.md             # 프로젝트 문서
```

## 빠른 시작

### Docker 사용 (가장 간단)

```bash
# 1. 프로젝트 클론 또는 다운로드
cd api_server

# 2. 필요한 디렉토리 생성
mkdir -p logs data

# 3. 서버 시작
docker compose up -d --build

# 4. 서버 확인
curl http://localhost:8000/health

# 5. Swagger UI 접속
# 브라우저에서 http://localhost:8000/docs 열기
```

**자세한 Docker 사용법은 [docs/DOCKER.md](docs/DOCKER.md)를 참조하세요.**

### Python 직접 사용

```bash
# 1. 가상 환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 데이터베이스 초기화
python scripts/init_db.py

# 4. 서버 시작
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

자세한 내용은 아래 섹션을 참조하세요.

## 사전 요구사항

### 필수
- Python 3.9+ (Docker 사용 시 불필요)
- SQLite 3 (Python에 포함됨)
- Ollama 서버 (1개 이상)

### 선택사항
- Docker 20.10+ 및 Docker Compose 2.0+ (Docker 사용 시)

## 설치

### 방법 1: Docker 사용 (권장)

Docker를 사용하면 환경 설정이 간단하고 일관됩니다:

```bash
# 1. 프로젝트 디렉토리로 이동
cd api_server

# 2. 필요한 디렉토리 생성
mkdir -p logs data

# 3. 서버 빌드 및 시작
docker compose up -d --build

# 4. 데이터베이스 초기화 (처음 한 번만)
docker compose exec tokamak-ai-api python scripts/init_db.py
```

**자세한 Docker 사용법은 [docs/DOCKER.md](docs/DOCKER.md)를 참조하세요.**

### 방법 2: Python 직접 설치

#### 1. 프로젝트 설정

```bash
# 프로젝트 디렉토리로 이동
cd api_server

# 가상 환경 생성
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

#### 2. 환경 설정

```bash
# 예제 환경 파일 복사 (있는 경우)
cp .env.example .env

# 설정 편집
nano .env  # 또는 원하는 에디터 사용
```

`.env` 파일에서 다음을 업데이트하세요:

```env
# Ollama 백엔드 서버
OLLAMA_SERVERS=http://192.168.1.101:11434,http://192.168.1.102:11434,http://192.168.1.103:11434

# 데이터베이스 (SQLite - 기본값, 추가 설정 불필요)
DATABASE_URL=sqlite+aiosqlite:///./tokamak_ai_api.db

# 보안 (안전한 시크릿 키 생성)
SECRET_KEY=$(openssl rand -hex 32)

# 속도 제한
DEFAULT_RATE_LIMIT=1000
RATE_LIMIT_WINDOW=3600

# 로깅
LOG_LEVEL=INFO
```

#### 3. 데이터베이스 초기화

```bash
# 데이터베이스 테이블 및 기본 관리자 계정 생성
python scripts/init_db.py
```

이 명령은 기본 관리자 계정을 생성하고 관리자 API 키를 표시합니다. **이 키를 안전하게 저장하세요!**

**참고**: Docker를 사용하는 경우, 데이터베이스 파일은 `./data` 디렉토리에 저장됩니다.

## 서버 실행

### 방법 1: Docker 사용 (권장)

가장 간단하고 일관된 방법입니다:

```bash
# 빌드 및 실행
docker compose up -d --build

# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f tokamak-ai-api
```

**자세한 Docker 사용법은 [docs/DOCKER.md](docs/DOCKER.md)를 참조하세요.**

### 방법 2: 빠른 시작 (run.sh 사용)

```bash
# 스크립트 실행 권한 부여
chmod +x scripts/run.sh

# 서버 시작 (의존성 및 데이터베이스 자동 확인)
./scripts/run.sh
```

스크립트는 다음을 수행합니다:
- 필요시 가상 환경 생성
- 자동으로 의존성 설치
- 데이터베이스 연결 확인
- 필요시 데이터베이스 초기화
- 서버 시작

### 방법 3: 개발 모드 (수동)

```bash
# 가상 환경 활성화
source venv/bin/activate  # Windows: venv\Scripts\activate

# uvicorn으로 직접 실행 (권장)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 또는 Python으로 실행
python main.py
```

### Systemd를 사용한 프로덕션 모드

systemd 서비스 파일 생성:

```bash
sudo nano /etc/systemd/system/tokamak-ai-api.service
```

```ini
[Unit]
Description=Tokamak AI API Server
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tokamak-ai-api-server
Environment="PATH=/path/to/tokamak-ai-api-server/venv/bin"
ExecStart=/path/to/tokamak-ai-api-server/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable tokamak-ai-api
sudo systemctl start tokamak-ai-api

# 상태 확인
sudo systemctl status tokamak-ai-api

# 로그 보기
sudo journalctl -u tokamak-ai-api -f
```

### Gunicorn을 사용한 프로덕션 모드 (권장)

```bash
# gunicorn 설치
pip install gunicorn

# 4개 워커로 실행
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/tokamak-ai-api/access.log \
  --error-logfile /var/log/tokamak-ai-api/error.log
```

## API 키 관리

### 팀원용 API 키 생성

```bash
# 사용자 키 생성
python scripts/generate_api_key.py kevin --role user --rate-limit 1000

# 관리자 키 생성
python scripts/generate_api_key.py admin_user --role admin --rate-limit 10000

# 설명과 함께 생성
python scripts/generate_api_key.py developer1 --role user --rate-limit 500 --description "프론트엔드 개발자"
```

### API 사용 (관리자 엔드포인트)

```bash
# API 키 생성 (관리자 키 필요)
curl -X POST http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer1",
    "role": "user",
    "rate_limit": 1000,
    "description": "개발자 접근"
  }'

# 모든 API 키 목록 조회
curl http://localhost:8000/admin/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_KEY"

# API 키 취소
curl -X DELETE http://localhost:8000/admin/api-keys/developer1 \
  -H "Authorization: Bearer YOUR_ADMIN_KEY"
```

## 클라이언트 사용법

### Python 예제

```python
import requests

API_KEY = "sk-xxxxxxxxxxxxx"
API_URL = "http://localhost:8000"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 완성 생성
response = requests.post(
    f"{API_URL}/api/generate",
    headers=headers,
    json={
        "model": "deepseek-coder:33b",
        "prompt": "피보나치 수를 계산하는 함수를 작성하세요",
        "stream": False
    }
)

print(response.json())
```

### 스트리밍 예제

```python
import requests
import json

response = requests.post(
    f"{API_URL}/api/generate",
    headers=headers,
    json={
        "model": "deepseek-coder:33b",
        "prompt": "재귀를 설명하세요",
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line)
        print(data.get("response", ""), end="", flush=True)
```

### 채팅 API 예제

```python
response = requests.post(
    f"{API_URL}/api/chat",
    headers=headers,
    json={
        "model": "deepseek-coder:33b",
        "messages": [
            {"role": "user", "content": "스마트 컨트랙트란 무엇인가요?"},
            {"role": "assistant", "content": "스마트 컨트랙트는..."},
            {"role": "user", "content": "Solidity로 어떻게 작성하나요?"}
        ],
        "stream": False
    }
)

print(response.json())
```

### cURL 예제

```bash
# 완성 생성
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder:33b",
    "prompt": "Python으로 hello world를 작성하세요",
    "stream": false
  }'

# 사용 가능한 모델 목록 조회
curl http://localhost:8000/api/tags \
  -H "Authorization: Bearer YOUR_API_KEY"

# 사용량 확인
curl http://localhost:8000/usage/me \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 모니터링 및 관리

### 헬스 체크

```bash
curl http://localhost:8000/health
```

### 서버 상태 (관리자 전용)

```bash
curl http://localhost:8000/status \
  -H "Authorization: Bearer YOUR_ADMIN_KEY"
```

### 사용량 통계

```bash
# 본인 사용량
curl http://localhost:8000/usage/me \
  -H "Authorization: Bearer YOUR_API_KEY"

# 사용자 사용량 (관리자 전용)
curl http://localhost:8000/admin/usage/developer1?days=7 \
  -H "Authorization: Bearer YOUR_ADMIN_KEY"
```

## 설정 옵션

### 속도 제한 (Rate Limiting)

**기본 설정: 시간당(per hour) 제한**

속도 제한은 기본적으로 **시간당(1시간)** 기준으로 작동합니다.

```env
DEFAULT_RATE_LIMIT=1000        # 기본 시간당 요청 수 (1시간에 1000개 요청)
RATE_LIMIT_WINDOW=3600         # 윈도우 시간(초) - 기본값: 3600초 = 1시간
```

**작동 방식:**
- 윈도우는 매 시간 정각(0분 0초)에 리셋됩니다
- 예: 오후 2시 30분에 요청하면, 오후 3시 0분까지의 윈도우에서 카운트됩니다
- 오후 3시 0분이 되면 카운터가 리셋되고 새로운 윈도우가 시작됩니다

**윈도우 시간 변경:**

다른 시간 단위로 변경하려면 `RATE_LIMIT_WINDOW`를 조정하세요:

```env
# 30분당 제한으로 변경
RATE_LIMIT_WINDOW=1800         # 30분 = 1800초

# 일일 제한으로 변경
RATE_LIMIT_WINDOW=86400        # 24시간 = 86400초

# 10분당 제한으로 변경
RATE_LIMIT_WINDOW=600          # 10분 = 600초
```

**예시:**
- `DEFAULT_RATE_LIMIT=1000`, `RATE_LIMIT_WINDOW=3600`: 시간당 1000개 요청
- `DEFAULT_RATE_LIMIT=500`, `RATE_LIMIT_WINDOW=1800`: 30분당 500개 요청
- `DEFAULT_RATE_LIMIT=10000`, `RATE_LIMIT_WINDOW=86400`: 일일 10,000개 요청

**사용자별 속도 제한:**

각 사용자는 개별적으로 속도 제한을 설정할 수 있습니다:

```bash
# Python 직접 사용 시
python scripts/generate_api_key.py user1 --rate-limit 2000

# Docker 사용 시 (자세한 내용은 docs/DOCKER.md 참조)
docker compose exec tokamak-ai-api python scripts/generate_api_key.py user1 --rate-limit 2000
```

**속도 제한 확인:**

```bash
# 현재 사용량 확인
curl http://localhost:8000/usage/me \
  -H "Authorization: Bearer YOUR_API_KEY"
```

응답 예시:
```json
{
  "username": "kevin",
  "rate_limit": 1000,
  "current_hour_usage": 45,
  "remaining": 955,
  "recent_requests": [...]
}
```

### 로드 밸런싱

서버는 기본적으로 **최소 연결 수** 알고리즘을 사용합니다. 백엔드 서버는 30초마다 자동으로 헬스 체크됩니다.

헬스 체크 간격을 변경하려면 `app/load_balancer.py`를 편집하세요:

```python
await asyncio.sleep(30)  # 이 값을 변경하세요
```

### 로깅

`.env`에서 로깅 설정:

```env
LOG_LEVEL=INFO                              # DEBUG, INFO, WARNING, ERROR
LOG_FILE=/var/log/tokamak-ai-api/server.log    # 로그 파일 경로
```

## 데이터베이스 쿼리

### 최근 사용량 보기

```bash
# SQLite 데이터베이스 위치: ./tokamak_ai_api.db
# sqlite3 명령줄 도구 사용

sqlite3 tokamak_ai_api.db

-- 최근 요청 보기
SELECT username, model, endpoint, total_tokens, duration_ms, success, timestamp
FROM usage_logs
ORDER BY timestamp DESC
LIMIT 20;

-- 사용자별 사용량 (최근 7일)
SELECT 
    username,
    COUNT(*) as total_requests,
    SUM(total_tokens) as total_tokens,
    AVG(duration_ms) as avg_duration_ms,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_requests
FROM usage_logs
WHERE timestamp > datetime('now', '-7 days')
GROUP BY username
ORDER BY total_requests DESC;

-- 가장 많이 사용된 모델
SELECT model, COUNT(*) as usage_count
FROM usage_logs
WHERE timestamp > datetime('now', '-7 days')
GROUP BY model
ORDER BY usage_count DESC;
```

## 문제 해결

### 백엔드 연결 문제

```bash
# Ollama 서버가 실행 중인지 확인
curl http://192.168.1.101:11434/api/tags

# 로드 밸런서 상태 보기
curl http://localhost:8000/status -H "Authorization: Bearer ADMIN_KEY"
```

### 속도 제한 문제

```bash
# 사용자의 속도 제한 초기화 (SQLite)
sqlite3 tokamak_ai_api.db
> DELETE FROM rate_limits WHERE username='username';
> .quit
```

### 데이터베이스 연결 문제

```bash
# 데이터베이스 연결 테스트
python -c "
import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select

async def test():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(1))
        print('데이터베이스 연결 성공!')

asyncio.run(test())
"
```

## 성능 튜닝

### 30명 이상 동시 사용자

```env
# 워커 수 증가
WORKERS=8

# SQLite는 WAL 모드에서 동시 읽기를 잘 처리합니다
# 중간 정도의 부하에는 추가 설정이 필요하지 않습니다
```

## 보안 모범 사례

1. **프로덕션에서는 항상 HTTPS 사용** - SSL이 있는 Nginx 리버스 프록시 추가
2. **강력한 SECRET_KEY** - `openssl rand -hex 32`로 생성
3. **정기적인 백업** - SQLite 데이터베이스 파일 정기 백업 (`tokamak_ai_api.db`)
4. **API 키 순환** - 주기적으로 키 교체
5. **로그 모니터링** - 의심스러운 활동 감시
6. **데이터베이스 파일 권한** - SQLite 데이터베이스 파일에 적절한 권한 설정

## Docker 사용

> **참고**: Docker 없이도 사용할 수 있습니다! 위의 "설치" 섹션을 따라하면 Python만으로 바로 실행할 수 있습니다. Docker는 프로덕션 배포나 환경 일관성이 필요할 때 사용하세요.

### 빠른 시작

```bash
# 필요한 디렉토리 생성
mkdir -p logs data

# Docker 이미지 빌드 및 서버 시작
docker compose up -d --build

# 서버 상태 확인
docker compose ps

# 헬스체크 확인
curl http://localhost:8000/health
```

### 자세한 Docker 가이드

**모든 Docker 관련 내용은 [docs/DOCKER.md](docs/DOCKER.md)를 참조하세요.**

포함된 내용:
- 환경 변수 설정 (`.env` 파일)
- 시크릿 키 설정
- 데이터베이스 초기화
- 유저(API 키) 관리
- 유용한 Docker 명령어
- 문제 해결
- Nginx 설정

## Nginx 추가 (프로덕션 권장 - 선택사항)

Nginx는 Docker Compose 프로파일을 사용하여 선택적 서비스로 포함되어 있습니다.

### Docker Compose 사용 (권장)

```bash
# nginx와 함께 시작
docker compose --profile production up -d
```

**자세한 내용은 [docs/DOCKER.md](docs/DOCKER.md#nginx-추가-프로덕션-권장---선택사항)를 참조하세요.**

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

## 라이선스

MIT License

## 지원

문제나 질문이 있으면 인프라 팀에 문의하거나 로그를 확인하세요:

```bash
# Docker 사용 시
docker compose logs -f tokamak-ai-api

# Systemd 사용 시
sudo journalctl -u tokamak-ai-api -f

# 직접 실행 시
# 로그는 콘솔에 출력되거나 설정된 로그 파일에 기록됩니다
tail -f /var/log/tokamak-ai-api/server.log

# Nginx 로그 (프로덕션 모드)
docker compose logs -f nginx
# 또는
tail -f logs/nginx/access.log
tail -f logs/nginx/error.log
```
