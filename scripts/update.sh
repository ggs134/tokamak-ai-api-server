#!/bin/bash

# Tokamak AI API Server Update Script
# Updates application code and dependencies without overwriting configuration

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Tokamak AI API Server Update         ║${NC}"
echo -e "${GREEN}╔════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root${NC}"
   exit 1
fi

# Check if application is already deployed
APP_DIR="/opt/tokamak-ai-api"

if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}Error: Application not found at $APP_DIR${NC}"
    echo -e "${YELLOW}Please run deploy.sh first to install the application.${NC}"
    exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
    echo -e "${RED}Error: .env file not found at $APP_DIR/.env${NC}"
    echo -e "${YELLOW}Please run deploy.sh first to configure the application.${NC}"
    exit 1
fi

echo -e "${GREEN}Found existing installation at: $APP_DIR${NC}"
echo ""

# Backup current .env file
echo -e "${YELLOW}[1/5] Backing up configuration...${NC}"
cp "$APP_DIR/.env" "$APP_DIR/.env.backup.$(date +%Y%m%d_%H%M%S)"
echo -e "${GREEN}✓ Configuration backed up${NC}"

# Stop service
echo -e "${YELLOW}[2/5] Stopping service...${NC}"
if systemctl is-active --quiet tokamak-ai-api 2>/dev/null; then
    sudo systemctl stop tokamak-ai-api
    echo -e "${GREEN}✓ Service stopped${NC}"
else
    echo -e "${YELLOW}Service was not running${NC}"
fi

# Update application files
echo -e "${YELLOW}[3/5] Updating application files...${NC}"
cd "$APP_DIR"

# Backup data directory
if [ -d "data" ]; then
    echo "Backing up data directory..."
    tar -czf "data.backup.$(date +%Y%m%d_%H%M%S).tar.gz" data/ 2>/dev/null || true
fi

# Copy new files (preserve .env and data)
if [ -d "../app" ] || [ -d "../../app" ]; then
    # Find project root (could be parent or grandparent)
    if [ -d "../app" ]; then
        PROJECT_ROOT="$(cd .. && pwd)"
    elif [ -d "../../app" ]; then
        PROJECT_ROOT="$(cd ../.. && pwd)"
    else
        echo -e "${YELLOW}Warning: Could not find project root. Please run from project directory.${NC}"
        read -p "Continue with manual update? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        PROJECT_ROOT="."
    fi
    
    echo "Copying files from $PROJECT_ROOT..."
    cp -r "$PROJECT_ROOT/app" "$PROJECT_ROOT/config" "$PROJECT_ROOT/docs" "$PROJECT_ROOT/scripts" "$PROJECT_ROOT/tests" "$PROJECT_ROOT/main.py" "$PROJECT_ROOT/requirements.txt" "$PROJECT_ROOT/Dockerfile" "$PROJECT_ROOT/docker-compose.yml" . 2>/dev/null || true
    echo -e "${GREEN}✓ Files updated${NC}"
else
    echo -e "${YELLOW}Warning: Could not find source files.${NC}"
    echo "Please ensure you run this script from the project root directory."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Restore .env file (don't overwrite existing configuration)
if [ -f ".env.backup."* ]; then
    LATEST_BACKUP=$(ls -t .env.backup.* 2>/dev/null | head -1)
    if [ -n "$LATEST_BACKUP" ]; then
        cp "$LATEST_BACKUP" .env
        echo -e "${GREEN}✓ Configuration restored${NC}"
    fi
fi

# Update dependencies
echo -e "${YELLOW}[4/5] Updating dependencies...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt --upgrade
    echo -e "${GREEN}✓ Dependencies updated${NC}"
else
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo -e "${YELLOW}Creating new virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Update systemd service file (if start.sh exists, use it)
if [ -f "start.sh" ]; then
    echo -e "${YELLOW}Updating systemd service...${NC}"
    sudo tee /etc/systemd/system/tokamak-ai-api.service > /dev/null << EOF
[Unit]
Description=Tokamak AI API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/start.sh
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Service file updated${NC}"
fi

# Restart service
echo -e "${YELLOW}[5/5] Restarting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl restart tokamak-ai-api

# Wait for service to start
sleep 3

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Update Complete!                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Check service status
if systemctl is-active --quiet tokamak-ai-api; then
    echo -e "Service status: ${GREEN}$(sudo systemctl is-active tokamak-ai-api)${NC}"
    echo -e "API endpoint: ${GREEN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    
    # Test health endpoint
    sleep 2
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Health check passed${NC}"
    else
        echo -e "${YELLOW}⚠ Health check failed. Check logs: sudo journalctl -u tokamak-ai-api -f${NC}"
    fi
else
    echo -e "${RED}Service failed to start. Check logs:${NC}"
    echo "  sudo journalctl -u tokamak-ai-api -n 50"
fi

echo ""
echo "Useful commands:"
echo "  sudo systemctl status tokamak-ai-api    # Check status"
echo "  sudo journalctl -u tokamak-ai-api -f    # View logs"
echo "  sudo systemctl restart tokamak-ai-api   # Restart service"
echo ""
