# Admin 사용자 생성 스크립트 사용법

## 개요

`create_admin.sh` 스크립트는 데이터베이스에 직접 admin 사용자를 생성합니다.
서버가 실행 중이 아니어도 사용할 수 있습니다.

## 사용법

### 기본 사용 (대화형)

```bash
./scripts/create_admin.sh
```

스크립트가 다음 정보를 입력받습니다:
- 사용자 이름 (기본값: admin)
- Rate Limit (기본값: 10000)
- 설명 (선택사항)

### 명령줄 인자 사용

```bash
# 사용자 이름만 지정
./scripts/create_admin.sh myadmin

# 사용자 이름과 Rate Limit 지정
./scripts/create_admin.sh myadmin 5000
```

### 데이터베이스 경로 직접 지정

```bash
DB_PATH=/path/to/tokamak_ai_api.db ./scripts/create_admin.sh
```

## Docker 환경에서 사용

```bash
# 컨테이너 내에서 실행
docker compose exec tokamak-ai-api bash -c "cd /app && ./scripts/create_admin.sh"

# 또는 호스트에서 데이터베이스 파일 직접 접근
DB_PATH=./data/tokamak_ai_api.db ./scripts/create_admin.sh
```

## 예시

```bash
# 1. 기본 admin 생성
./scripts/create_admin.sh

# 2. 특정 이름의 admin 생성
./scripts/create_admin.sh backup_admin

# 3. 높은 Rate Limit으로 생성
./scripts/create_admin.sh super_admin 50000

# 4. 설명과 함께 생성
./scripts/create_admin.sh
# 사용자 이름: emergency_admin
# Rate Limit: 10000
# 설명: 비상시 사용할 관리자 계정
```

## 출력 예시

```
╔════════════════════════════════════════╗
║  Admin 사용자 생성                     ║
╚════════════════════════════════════════╝

사용자 이름 (기본값: admin): myadmin
Rate Limit (기본값: 10000): 5000
설명 (선택사항): 테스트용 관리자

✓ 데이터베이스 파일 발견: /app/data/tokamak_ai_api.db

============================================================
Admin 사용자 생성 완료!
============================================================
사용자 이름:    myadmin
역할:          admin
Rate Limit:    5000 requests/hour
설명:          테스트용 관리자

API Key:     sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
============================================================

⚠️  중요: 이 API 키를 안전하게 저장하세요!
     이 키는 다시 표시되지 않습니다.
============================================================
```

## 주의사항

- 생성된 API 키는 **한 번만 표시**됩니다. 안전하게 저장하세요.
- 동일한 사용자 이름이 이미 존재하는 경우 덮어쓸지 물어봅니다.
- 데이터베이스 파일을 찾지 못하면 여러 경로를 시도합니다.
- 서버가 실행 중이 아니어도 사용할 수 있습니다.

## 문제 해결

### 데이터베이스 파일을 찾을 수 없는 경우

```bash
# 1. 데이터베이스 파일 위치 확인
find /opt -name tokamak_ai_api.db 2>/dev/null
find . -name tokamak_ai_api.db 2>/dev/null

# 2. 경로 직접 지정
DB_PATH=/path/to/tokamak_ai_api.db ./scripts/create_admin.sh
```

### 권한 오류가 발생하는 경우

```bash
# 데이터베이스 파일 권한 확인
ls -la tokamak_ai_api.db

# 필요시 권한 변경
chmod 644 tokamak_ai_api.db
chown $USER:$USER tokamak_ai_api.db
```
