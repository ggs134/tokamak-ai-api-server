# 설치 가이드

## 빠른 비교

| 방법 | 최적 용도 | 복잡도 | 요구사항 |
|--------|----------|------------|--------------|
| **Docker** | 프로덕션, 쉬운 배포 | 낮음 | Docker, Docker Compose |
| **수동** | 개발, 커스텀 설정 | 중간 | Python 3.9+, SQLite |

## 옵션 1: Docker (프로덕션 권장)

Docker 설치 방법은 [QUICKSTART.md](QUICKSTART.md)를 참조하세요.

**장점:**
- 격리된 환경
- 쉬운 배포
- 시스템 간 일관성
- nginx 옵션 포함

**단점:**
- Docker 필요
- 약간 더 많은 리소스 사용

## 옵션 2: 수동 설치 (Docker 없음)

### 사전 요구사항

- **Python 3.9+** (Python 3.11+ 권장)
- **SQLite 3** (보통 Python에 포함됨)
- **pip** (Python 패키지 관리자)

### 단계별 설치

#### 1. 프로젝트 클론 또는 다운로드

```bash
git clone <repository-url>
cd api_server
```

또는 프로젝트 파일을 다운로드하고 압축 해제하세요.

#### 2. 가상 환경 생성

```bash
# 가상 환경 생성
python3 -m venv venv

# 가상 환경 활성화
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

#### 3. 의존성 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. 환경 설정

`.env` 파일 생성:

```bash
cp .env.example .env
nano .env  # 또는 선호하는 에디터 사용
```

최소 필수 설정:

```env
# Ollama 백엔드 서버 (쉼표로 구분)
OLLAMA_SERVERS=http://localhost:11434

# 데이터베이스 (SQLite - 기본값)
DATABASE_URL=sqlite+aiosqlite:///./tokamak_ai_api.db

# 보안 (생성 방법: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# 선택사항: 속도 제한
DEFAULT_RATE_LIMIT=1000
RATE_LIMIT_WINDOW=3600
```

#### 5. 데이터베이스 초기화

```bash
python scripts/init_db.py
```

이 명령은 다음을 수행합니다:
- 데이터베이스 테이블 생성
- 기본 관리자 계정 생성
- 관리자 API 키 표시 (안전하게 저장하세요!)

#### 6. 서버 시작

**run.sh 사용 (권장):**
```bash
chmod +x run.sh
./run.sh
```

**수동 시작:**
```bash
# 가상 환경이 활성화되어 있는지 확인
source venv/bin/activate

# 서버 시작
python -m app.main

# 또는 uvicorn으로 직접 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 7. 설치 확인

```bash
# 헬스 체크
curl http://localhost:8000/health

# status: "ok"가 포함된 JSON이 반환되어야 합니다
```

### 서비스로 실행 (프로덕션 - Linux)

Linux에서 systemd 서비스로 실행:

`/etc/systemd/system/tokamak-ai-api.service` 생성:

```ini
[Unit]
Description=Tokamak AI API Server
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/api_server
Environment="PATH=/path/to/api_server/venv/bin"
ExecStart=/path/to/api_server/venv/bin/python -m app.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

활성화 및 시작:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tokamak-ai-api
sudo systemctl start tokamak-ai-api

# 상태 확인
sudo systemctl status tokamak-ai-api

# 로그 보기
sudo journalctl -u tokamak-ai-api -f
```

### 문제 해결

#### 데이터베이스 문제

```bash
# 데이터베이스 파일 존재 확인
ls -la tokamak_ai_api.db

# 데이터베이스 재초기화
python scripts/init_db.py

# 데이터베이스 무결성 확인
sqlite3 tokamak_ai_api.db "PRAGMA integrity_check;"
```

#### 포트가 이미 사용 중

```bash
# 포트 8000을 사용하는 프로세스 찾기
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# .env에서 포트 변경
PORT=8001
```

#### 권한 문제

```bash
# 스크립트 실행 권한 부여
chmod +x run.sh
chmod +x scripts/init_db.py

# 데이터베이스 권한 수정
chmod 644 tokamak_ai_api.db
```

### 업데이트

```bash
# 최신 변경사항 가져오기
git pull

# 의존성 업데이트
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 서비스 재시작
sudo systemctl restart tokamak-ai-api  # Linux
```

### 제거

```bash
# 서비스 중지
sudo systemctl stop tokamak-ai-api
sudo systemctl disable tokamak-ai-api

# 서비스 파일 제거
sudo rm /etc/systemd/system/tokamak-ai-api.service

# 애플리케이션 파일 제거
rm -rf /path/to/api_server
```

## 다음 단계

- API 사용법은 [README.md](../README.md) 참조
- 빠른 시작 가이드는 [QUICKSTART.md](QUICKSTART.md) 참조
- 아키텍처 세부사항은 [ARCHITECTURE.md](ARCHITECTURE.md) 참조
