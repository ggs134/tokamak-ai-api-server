#!/bin/bash

# Docker 환경에서 운영 서버 업데이트 스크립트

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Docker 환경 업데이트                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# 현재 디렉토리 확인
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# 백업
echo -e "${YELLOW}[1/5] 백업 중...${NC}"
if [ -f "data/tokamak_ai_api.db" ]; then
    BACKUP_FILE="data/tokamak_ai_api.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp data/tokamak_ai_api.db "$BACKUP_FILE"
    echo -e "${GREEN}✓ 데이터베이스 백업: $BACKUP_FILE${NC}"
fi

if [ -f ".env" ]; then
    ENV_BACKUP=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env "$ENV_BACKUP"
    echo -e "${GREEN}✓ 설정 파일 백업: $ENV_BACKUP${NC}"
fi

# Git 업데이트 확인
echo -e "${YELLOW}[2/5] 코드 업데이트 확인...${NC}"
if [ -d ".git" ]; then
    echo "현재 커밋: $(git rev-parse --short HEAD)"
    read -p "최신 코드로 업데이트하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git pull origin main
        echo -e "${GREEN}✓ 코드 업데이트 완료${NC}"
    fi
else
    echo -e "${YELLOW}Git 저장소가 아닙니다. 수동으로 코드를 업데이트하세요.${NC}"
fi

# 데이터베이스 마이그레이션
echo -e "${YELLOW}[3/5] 데이터베이스 마이그레이션 확인...${NC}"
docker compose exec -T tokamak-ai-api python -c "
import sqlite3
import sys

try:
    conn = sqlite3.connect('/app/data/tokamak_ai_api.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(usage_logs)')
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'prompt' not in columns:
        print('prompt 컬럼 추가 중...')
        cursor.execute('ALTER TABLE usage_logs ADD COLUMN prompt TEXT')
        conn.commit()
        print('✓ prompt 컬럼 추가 완료')
    else:
        print('✓ prompt 컬럼이 이미 존재합니다')
    
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'오류: {e}')
    sys.exit(1)
" 2>&1 || echo -e "${YELLOW}⚠ 마이그레이션 스킵 (컨테이너가 실행 중이지 않을 수 있음)${NC}"

# 이미지 재빌드
echo -e "${YELLOW}[4/5] Docker 이미지 재빌드...${NC}"
docker compose build tokamak-ai-api
echo -e "${GREEN}✓ 이미지 빌드 완료${NC}"

# 서비스 재시작
echo -e "${YELLOW}[5/5] 서비스 재시작...${NC}"
docker compose up -d --force-recreate tokamak-ai-api
echo -e "${GREEN}✓ 서비스 재시작 완료${NC}"

# 상태 확인
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  업데이트 완료!                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

sleep 3

# 헬스 체크
echo "서비스 상태 확인 중..."
if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✓ 컨테이너 실행 중${NC}"
    
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 헬스 체크 통과${NC}"
    else
        echo -e "${YELLOW}⚠ 헬스 체크 실패. 로그를 확인하세요.${NC}"
    fi
else
    echo -e "${RED}✗ 컨테이너가 실행되지 않습니다${NC}"
    echo "로그 확인: docker compose logs tokamak-ai-api"
fi

echo ""
echo "유용한 명령어:"
echo "  docker compose ps              # 상태 확인"
echo "  docker compose logs -f tokamak-ai-api  # 로그 확인"
echo "  docker compose restart tokamak-ai-api  # 재시작"
