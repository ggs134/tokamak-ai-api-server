#!/bin/bash

# Tokamak AI API Server Restart Script
# Automatically detects and restarts the server based on how it's running

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Tokamak AI API Server Restart         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root directory
cd "$PROJECT_ROOT"

# Function to check if systemd service exists and is active
check_systemd() {
    if systemctl list-unit-files | grep -q "tokamak-ai-api.service"; then
        if systemctl is-active --quiet tokamak-ai-api 2>/dev/null; then
            return 0  # Service exists and is active
        elif systemctl is-enabled --quiet tokamak-ai-api 2>/dev/null; then
            return 1  # Service exists but not active
        fi
    fi
    return 2  # Service doesn't exist
}

# Function to check if Docker container is running
check_docker() {
    if command -v docker &> /dev/null; then
        if docker compose ps 2>/dev/null | grep -q "tokamak-ai-api.*Up"; then
            return 0  # Container is running
        elif docker compose ps 2>/dev/null | grep -q "tokamak-ai-api"; then
            return 1  # Container exists but not running
        fi
    fi
    return 2  # Docker not available or container doesn't exist
}

# Function to check if process is running directly
check_direct() {
    if pgrep -f "python.*main.py" > /dev/null 2>&1 || pgrep -f "uvicorn.*main:app" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Detect how the server is running
RESTART_METHOD=""

echo -e "${YELLOW}Detecting server status...${NC}"

# Check systemd first
SYSTEMD_STATUS=$(check_systemd)
if [ $? -eq 0 ]; then
    RESTART_METHOD="systemd"
    echo -e "${GREEN}✓ Detected: systemd service${NC}"
elif [ $SYSTEMD_STATUS -eq 1 ]; then
    RESTART_METHOD="systemd"
    echo -e "${YELLOW}⚠ Detected: systemd service (not running)${NC}"
fi

# Check Docker if systemd not found
if [ -z "$RESTART_METHOD" ]; then
    DOCKER_STATUS=$(check_docker)
    if [ $? -eq 0 ]; then
        RESTART_METHOD="docker"
        echo -e "${GREEN}✓ Detected: Docker container${NC}"
    elif [ $DOCKER_STATUS -eq 1 ]; then
        RESTART_METHOD="docker"
        echo -e "${YELLOW}⚠ Detected: Docker container (not running)${NC}"
    fi
fi

# Check direct process if neither systemd nor Docker
if [ -z "$RESTART_METHOD" ]; then
    if check_direct; then
        RESTART_METHOD="direct"
        echo -e "${GREEN}✓ Detected: Direct Python process${NC}"
    else
        echo -e "${YELLOW}⚠ No running server detected${NC}"
        echo ""
        echo "Available options:"
        echo "  1. Start with systemd (if configured)"
        echo "  2. Start with Docker"
        echo "  3. Start directly with Python"
        echo ""
        read -p "Choose option (1-3) or press Enter to exit: " choice
        
        case $choice in
            1)
                RESTART_METHOD="systemd"
                ;;
            2)
                RESTART_METHOD="docker"
                ;;
            3)
                RESTART_METHOD="direct"
                ;;
            *)
                echo "Exiting..."
                exit 0
                ;;
        esac
    fi
fi

echo ""

# Restart based on detected method
case $RESTART_METHOD in
    systemd)
        echo -e "${YELLOW}Restarting systemd service...${NC}"
        if systemctl is-active --quiet tokamak-ai-api 2>/dev/null; then
            sudo systemctl restart tokamak-ai-api
            echo -e "${GREEN}✓ Service restarted${NC}"
        else
            sudo systemctl start tokamak-ai-api
            echo -e "${GREEN}✓ Service started${NC}"
        fi
        
        # Wait a moment and check status
        sleep 2
        if systemctl is-active --quiet tokamak-ai-api; then
            echo -e "${GREEN}✓ Service is running${NC}"
            echo ""
            echo "Service status:"
            sudo systemctl status tokamak-ai-api --no-pager -l | head -10
        else
            echo -e "${RED}✗ Service failed to start${NC}"
            echo "Check logs with: sudo journalctl -u tokamak-ai-api -n 50"
            exit 1
        fi
        ;;
        
    docker)
        echo -e "${YELLOW}Restarting Docker container...${NC}"
        if docker compose ps 2>/dev/null | grep -q "tokamak-ai-api.*Up"; then
            docker compose restart tokamak-ai-api
            echo -e "${GREEN}✓ Container restarted${NC}"
        else
            docker compose up -d tokamak-ai-api
            echo -e "${GREEN}✓ Container started${NC}"
        fi
        
        # Wait a moment and check status
        sleep 3
        if docker compose ps 2>/dev/null | grep -q "tokamak-ai-api.*Up"; then
            echo -e "${GREEN}✓ Container is running${NC}"
            echo ""
            echo "Container status:"
            docker compose ps tokamak-ai-api
        else
            echo -e "${RED}✗ Container failed to start${NC}"
            echo "Check logs with: docker compose logs tokamak-ai-api"
            exit 1
        fi
        ;;
        
    direct)
        echo -e "${YELLOW}Stopping existing processes...${NC}"
        # Find and kill existing processes
        pkill -f "python.*main.py" 2>/dev/null || true
        pkill -f "uvicorn.*main:app" 2>/dev/null || true
        sleep 1
        
        echo -e "${YELLOW}Starting server directly...${NC}"
        
        # Check if virtual environment exists
        if [ ! -d "venv" ]; then
            echo -e "${RED}Virtual environment not found!${NC}"
            echo "Please create it first: python3 -m venv venv"
            exit 1
        fi
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Check if .env exists
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}Warning: .env file not found${NC}"
        fi
        
        # Start server in background
        echo -e "${GREEN}Starting server on http://0.0.0.0:8000${NC}"
        nohup python main.py > logs/server.log 2>&1 &
        SERVER_PID=$!
        
        # Wait a moment and check if process is still running
        sleep 2
        if ps -p $SERVER_PID > /dev/null; then
            echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"
            echo "Logs: tail -f logs/server.log"
        else
            echo -e "${RED}✗ Server failed to start${NC}"
            echo "Check logs: cat logs/server.log"
            exit 1
        fi
        ;;
esac

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Restart Complete!                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
sleep 2

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo ""
    echo "Server is running at: http://localhost:8000"
    echo "API docs: http://localhost:8000/docs"
else
    echo -e "${YELLOW}⚠ Health check failed (server may still be starting)${NC}"
    echo "Wait a few seconds and check: curl http://localhost:8000/health"
fi

echo ""
echo "Useful commands:"
case $RESTART_METHOD in
    systemd)
        echo "  sudo systemctl status tokamak-ai-api    # Check status"
        echo "  sudo journalctl -u tokamak-ai-api -f    # View logs"
        ;;
    docker)
        echo "  docker compose ps                        # Check status"
        echo "  docker compose logs -f tokamak-ai-api  # View logs"
        ;;
    direct)
        echo "  ps aux | grep 'python.*main.py'          # Check process"
        echo "  tail -f logs/server.log                  # View logs"
        echo "  kill $SERVER_PID                         # Stop server"
        ;;
esac
echo ""
