#!/bin/bash

# Tokamak AI API Server Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root directory
cd "$PROJECT_ROOT"

echo -e "${GREEN}Starting Tokamak AI API Server...${NC}"
echo -e "${GREEN}Working directory: $PROJECT_ROOT${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found!${NC}"
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env with your configuration${NC}"
    exit 1
fi

# Check SQLite database connection
echo "Checking database connection..."
DB_CHECK_RESULT=$(python -c "
import asyncio
import sys
import signal
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.database import AsyncSessionLocal
from sqlalchemy import select

def timeout_handler(signum, frame):
    raise TimeoutError('Database check timed out')

async def test():
    try:
        async with AsyncSessionLocal() as session:
            result = await asyncio.wait_for(session.execute(select(1)), timeout=3.0)
            await session.close()
        return True
    except Exception as e:
        print(f'Database error: {e}', file=sys.stderr)
        return False
    finally:
        try:
            from app.database import engine
            await engine.dispose()
        except:
            pass

try:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5초 타임아웃
    result = asyncio.run(test())
    signal.alarm(0)  # 타임아웃 취소
    sys.exit(0 if result else 1)
except (TimeoutError, KeyboardInterrupt):
    signal.alarm(0)
    sys.exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database connected${NC}"
else
    echo -e "${YELLOW}⚠ Database connection check failed or timed out${NC}"
    echo -e "${YELLOW}Continuing anyway... (database will be initialized if needed)${NC}"
fi

# Check if database is initialized
echo "Checking database schema..."
SCHEMA_CHECK_RESULT=$(python -c "
import asyncio
import sys
import signal
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.database import AsyncSessionLocal, APIKey
from sqlalchemy import select

def timeout_handler(signum, frame):
    raise TimeoutError('Schema check timed out')

async def check():
    try:
        async with AsyncSessionLocal() as session:
            result = await asyncio.wait_for(session.execute(select(APIKey).limit(1)), timeout=3.0)
            await session.close()
        return True
    except:
        return False
    finally:
        try:
            from app.database import engine
            await engine.dispose()
        except:
            pass

try:
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5초 타임아웃
    result = asyncio.run(check())
    signal.alarm(0)  # 타임아웃 취소
    sys.exit(0 if result else 1)
except (TimeoutError, KeyboardInterrupt):
    signal.alarm(0)
    sys.exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database initialized${NC}"
else
    echo -e "${YELLOW}Database not initialized. Running initialization...${NC}"
    python scripts/init_db.py
fi

# Create log directory if it doesn't exist
mkdir -p logs

# Start server
echo -e "${GREEN}Starting server on http://0.0.0.0:8000${NC}"
echo "Press Ctrl+C to stop"
echo ""

python main.py
