# 빠른 시작 가이드

5분 안에 Tokamak AI API Server를 실행하세요!

## 옵션 1: 수동 설치 (Docker 없음) - 가장 간단함

### 사전 요구사항
- Python 3.9+
- SQLite 3 (Python에 포함됨)

### 단계

1. **Python 환경 설정**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **환경 설정**
```bash
cp .env.example .env
nano .env

# 다음 값들을 업데이트:
# OLLAMA_SERVERS=http://your-ollama-server:11434
# DATABASE_URL=sqlite+aiosqlite:///./tokamak_ai_api.db
# SECRET_KEY=$(openssl rand -hex 32)
```

3. **데이터베이스 초기화**
```bash
python scripts/init_db.py
```

표시된 관리자 API 키를 저장하세요!

4. **서버 시작**

**옵션 A: run.sh 사용 (권장)**
```bash
chmod +x run.sh
./run.sh
```

**옵션 B: 수동 시작**
```bash
source venv/bin/activate
python -m app.main
```

완료! API 서버가 `http://localhost:8000`에서 실행 중입니다.

---

## 옵션 2: Docker (프로덕션 배포용)

### 사전 요구사항
- Docker 및 Docker Compose 설치됨
- 호스트 또는 접근 가능한 서버에서 Ollama 실행 중

### 단계

1. **프로젝트 클론 또는 다운로드**
```bash
cd tokamak-ai-api-server
```

2. **백엔드 서버 설정**
```bash
# docker-compose.yml 편집
# OLLAMA_SERVERS를 Ollama 백엔드 서버로 변경
# 예: http://192.168.1.101:11434,http://192.168.1.102:11434
```

3. **시크릿 키 생성**
```bash
export SECRET_KEY=$(openssl rand -hex 32)
echo "SECRET_KEY=$SECRET_KEY" > .env.docker
```

4. **서비스 시작**

**개발 모드 (nginx 없음):**
```bash
docker-compose up -d
```

**프로덕션 모드 (nginx 리버스 프록시 포함):**
```bash
docker-compose --profile production up -d
```

5. **데이터베이스 초기화 및 관리자 키 생성**
```bash
# 서비스가 정상 상태가 될 때까지 대기 (약 10초)
docker-compose exec tokamak-ai-api python scripts/init_db.py
```

관리자 API 키가 표시됩니다. **안전하게 저장하세요!**

6. **서버 테스트**

**개발 모드:**
```bash
curl http://localhost:8000/health
```

**프로덕션 모드 (nginx 포함):**
```bash
curl http://localhost/health
```

7. **사용자 API 키 생성**
```bash
# 팀원용 키 생성
docker-compose exec tokamak-ai-api python scripts/generate_api_key.py kevin --role user --rate-limit 1000
```

완료! API 서버가 실행 중입니다:
- **개발**: `http://localhost:8000` (직접 접근)
- **프로덕션**: `http://localhost` (nginx를 통해)

### 서비스 관리

```bash
# 로그 보기
docker-compose logs -f tokamak-ai-api

# 서비스 중지
docker-compose down

# 서비스 재시작
docker-compose restart

# 데이터베이스 보기 (선택사항)
sqlite3 ./data/tokamak_ai_api.db
```


## 첫 API 요청

curl로 설정 테스트:

```bash
# API 키 설정
export API_KEY="sk-xxxxxxxxxxxxx"

# 생성 테스트
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:120b",
    "prompt": "Python으로 hello world 함수를 작성하세요",
    "stream": false
  }'
```

또는 테스트 클라이언트 사용:

```bash
# scripts/test_client.py를 편집하고 API_KEY 설정
python scripts/test_client.py
```

---

## 다음 단계

1. **팀원용 API 키 생성**
   ```bash
   python scripts/generate_api_key.py developer1 --role user
   python scripts/generate_api_key.py developer2 --role user
   ```

2. **프로덕션 배포 설정**
   - SSL이 있는 Nginx 리버스 프록시 추가
   - systemd 서비스 설정
   - 로그 로테이션 설정
   - 방화벽 규칙 설정

3. **사용량 모니터링**
   ```bash
   # 사용량 확인
   curl http://localhost:8000/usage/me \
     -H "Authorization: Bearer $API_KEY"
   ```

4. **전체 문서 읽기**
   - [README.md](../README.md)에서 전체 문서 확인
   - 설정 옵션 확인
   - 모니터링 및 문제 해결 방법 학습

---

## 일반적인 문제

### "데이터베이스 연결 실패"
- SQLite 데이터베이스 파일이 존재하는지 확인: `ls -la tokamak_ai_api.db`
- `.env`의 데이터베이스 경로 확인 (should be `sqlite+aiosqlite:///./tokamak_ai_api.db`)
- 파일 권한 확인: `chmod 644 tokamak_ai_api.db`
- 데이터베이스 재초기화: `python scripts/init_db.py`

### "정상 서버 없음"
- Ollama 서버가 실행 중인지 확인
- `.env` 또는 `docker-compose.yml`의 서버 URL 확인
- 테스트: `curl http://your-ollama-server:11434/api/tags`

### "Authorization 헤더 필요"
- 헤더에 API 키 포함: `Authorization: Bearer YOUR_KEY`
- API 키가 유효한지 확인: 로그 확인 또는 데이터베이스 조회

---

## 도움 받기

- 애플리케이션 로그 확인
  - Docker: `docker-compose logs -f tokamak-ai-api`
  - 수동: `./run.sh` 또는 systemd 로그 확인
  
- `.env`에서 디버그 로깅 활성화: `LOG_LEVEL=DEBUG`

- 자세한 문제 해결은 [README.md](../README.md) 검토

- 문의: infrastructure@tokamak.network
