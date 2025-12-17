#!/bin/bash

# Tokamak AI API Server Deployment Script
# For separate API server deployment

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Tokamak AI API Server Deployment     ║${NC}"
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root${NC}"
   exit 1
fi

# Detect system resources
echo -e "${GREEN}Detecting system resources...${NC}"
CPU_CORES=$(nproc)
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
echo -e "  CPU Cores: ${GREEN}$CPU_CORES${NC}"
echo -e "  Total Memory: ${GREEN}${TOTAL_MEM}MB${NC}"
echo ""

# Install system dependencies
echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3-venv python3-pip nginx

# Create application directory
echo -e "${YELLOW}[2/6] Setting up application...${NC}"
APP_DIR="/opt/tokamak-ai-api"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Check if this is an update (existing installation)
IS_UPDATE=false
if [ -f "$APP_DIR/.env" ] && [ -d "$APP_DIR/venv" ]; then
    IS_UPDATE=true
    echo -e "${YELLOW}Existing installation detected. Running in update mode...${NC}"
    echo -e "${YELLOW}Configuration and data will be preserved.${NC}"
    read -p "Continue with update? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Update cancelled.${NC}"
        echo -e "${GREEN}Tip: Use scripts/update.sh for safer updates.${NC}"
        exit 0
    fi
fi

# Copy files
if [ -d "app" ]; then
    # Backup existing .env if updating
    if [ "$IS_UPDATE" = true ] && [ -f "$APP_DIR/.env" ]; then
        cp "$APP_DIR/.env" "$APP_DIR/.env.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${GREEN}✓ Existing .env backed up${NC}"
    fi
    
    cp -r app config docs scripts tests main.py requirements.txt Dockerfile docker-compose.yml $APP_DIR/ 2>/dev/null || true
    
    # Only copy .env.example if .env doesn't exist (first install)
    if [ ! -f "$APP_DIR/.env" ] && [ -f ".env.example" ]; then
        cp .env.example $APP_DIR/.env
    elif [ "$IS_UPDATE" = true ] && [ -f "$APP_DIR/.env.backup."* ]; then
        # Restore backed up .env
        LATEST_BACKUP=$(ls -t $APP_DIR/.env.backup.* 2>/dev/null | head -1)
        if [ -n "$LATEST_BACKUP" ]; then
            cp "$LATEST_BACKUP" "$APP_DIR/.env"
            echo -e "${GREEN}✓ Configuration restored${NC}"
        fi
    fi
fi

cd $APP_DIR

# Create data directory for SQLite
mkdir -p data

# Setup virtual environment
echo -e "${YELLOW}[3/6] Creating Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo -e "${GREEN}✓ Virtual environment ready${NC}"

# Configure environment
echo -e "${YELLOW}[4/6] Configuring environment...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}Created .env from .env.example${NC}"
    else
        echo -e "${RED}.env file not found and .env.example not available!${NC}"
        exit 1
    fi
fi

# For updates, preserve existing configuration
if [ "$IS_UPDATE" = true ]; then
    echo -e "${GREEN}Preserving existing configuration...${NC}"
    # Read existing values
    EXISTING_OLLAMA_SERVERS=$(grep "^OLLAMA_SERVERS=" .env | cut -d'=' -f2- || echo "")
    EXISTING_SECRET_KEY=$(grep "^SECRET_KEY=" .env | cut -d'=' -f2- || echo "")
    
    if [ -n "$EXISTING_OLLAMA_SERVERS" ]; then
        OLLAMA_SERVERS="$EXISTING_OLLAMA_SERVERS"
        echo -e "${GREEN}Using existing Ollama servers: $OLLAMA_SERVERS${NC}"
    else
        echo ""
        echo -e "${YELLOW}Enter your Ollama server URLs (comma-separated):${NC}"
        echo "Example: http://192.168.1.101:11434,http://192.168.1.102:11434"
        read -p "Ollama servers: " OLLAMA_SERVERS
    fi
    
    if [ -n "$EXISTING_SECRET_KEY" ]; then
        SECRET_KEY="$EXISTING_SECRET_KEY"
        echo -e "${GREEN}Preserving existing SECRET_KEY${NC}"
    else
        SECRET_KEY=$(openssl rand -hex 32)
    fi
else
    # First installation - prompt for configuration
    echo ""
    echo -e "${YELLOW}Enter your Ollama server URLs (comma-separated):${NC}"
    echo "Example: http://192.168.1.101:11434,http://192.168.1.102:11434"
    read -p "Ollama servers: " OLLAMA_SERVERS
    
    # Generate secret key
    SECRET_KEY=$(openssl rand -hex 32)
fi

# Calculate optimal worker count based on CPU cores
# Rule: 1 worker per 2 CPU cores, minimum 1, maximum 8
if [ "$CPU_CORES" -ge 16 ]; then
    WORKERS=8
elif [ "$CPU_CORES" -ge 12 ]; then
    WORKERS=6
elif [ "$CPU_CORES" -ge 8 ]; then
    WORKERS=4
elif [ "$CPU_CORES" -ge 4 ]; then
    WORKERS=2
else
    WORKERS=1
fi

# Adjust rate limit based on memory
if [ "$TOTAL_MEM" -ge 16384 ]; then
    DEFAULT_RATE_LIMIT=10000
elif [ "$TOTAL_MEM" -ge 8192 ]; then
    DEFAULT_RATE_LIMIT=5000
elif [ "$TOTAL_MEM" -ge 4096 ]; then
    DEFAULT_RATE_LIMIT=2000
elif [ "$TOTAL_MEM" -ge 2048 ]; then
    DEFAULT_RATE_LIMIT=1000
else
    DEFAULT_RATE_LIMIT=500
fi

echo -e "${GREEN}Performance optimization:${NC}"
echo -e "  Workers: ${GREEN}$WORKERS${NC} (based on $CPU_CORES CPU cores)"
echo -e "  Default Rate Limit: ${GREEN}$DEFAULT_RATE_LIMIT${NC} (based on ${TOTAL_MEM}MB RAM)"

# Update .env
sed -i "s|OLLAMA_SERVERS=.*|OLLAMA_SERVERS=$OLLAMA_SERVERS|" .env
sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
sed -i "s|DATABASE_URL=.*|DATABASE_URL=sqlite+aiosqlite:////$APP_DIR/data/tokamak_ai_api.db|" .env
sed -i "s|WORKERS=.*|WORKERS=$WORKERS|" .env
sed -i "s|DEFAULT_RATE_LIMIT=.*|DEFAULT_RATE_LIMIT=$DEFAULT_RATE_LIMIT|" .env

echo -e "${GREEN}✓ Environment configured${NC}"

# Initialize database (only if not updating or database doesn't exist)
echo -e "${YELLOW}[5/6] Initializing database...${NC}"
if [ "$IS_UPDATE" = true ] && [ -f "data/tokamak_ai_api.db" ]; then
    echo -e "${GREEN}Existing database found. Skipping initialization.${NC}"
    echo -e "${YELLOW}Note: Database schema will be updated automatically on startup.${NC}"
else
    python scripts/init_db.py
fi

# Create systemd service
echo -e "${YELLOW}[6/6] Setting up systemd service...${NC}"

sudo tee /etc/systemd/system/tokamak-ai-api.service > /dev/null << EOF
[Unit]
Description=Tokamak AI API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/tokamak-ai-api
sudo chown $USER:$USER /var/log/tokamak-ai-api

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable tokamak-ai-api

if [ "$IS_UPDATE" = true ]; then
    # Restart if already running, start if not
    if systemctl is-active --quiet tokamak-ai-api 2>/dev/null; then
        sudo systemctl restart tokamak-ai-api
        echo -e "${GREEN}✓ Service restarted${NC}"
    else
        sudo systemctl start tokamak-ai-api
        echo -e "${GREEN}✓ Service started${NC}"
    fi
else
    sudo systemctl start tokamak-ai-api
    echo -e "${GREEN}✓ Service started${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Deployment Complete!                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "Service status: ${GREEN}$(sudo systemctl is-active tokamak-ai-api)${NC}"
echo -e "API endpoint: ${GREEN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
echo ""
echo "System Configuration:"
echo "  CPU Cores: $CPU_CORES"
echo "  Workers: $WORKERS"
echo "  Total Memory: ${TOTAL_MEM}MB"
echo "  Default Rate Limit: $DEFAULT_RATE_LIMIT requests/hour"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status tokamak-ai-api    # Check status"
echo "  sudo systemctl restart tokamak-ai-api   # Restart service"
echo "  sudo journalctl -u tokamak-ai-api -f    # View logs"
echo ""
echo "Next steps:"
echo "  1. Configure firewall: sudo ufw allow 8000/tcp"
echo "  2. Setup Nginx reverse proxy (optional)"
echo "  3. Create API keys: python $APP_DIR/scripts/generate_api_key.py <username>"
echo ""
echo "To update the application later:"
echo "  1. Pull latest code: cd $APP_DIR && git pull (if using git)"
echo "  2. Run update script: ./scripts/update.sh"
echo "  3. Or manually:"
echo "     - Copy new files to $APP_DIR"
echo "     - Update dependencies: source venv/bin/activate && pip install -r requirements.txt --upgrade"
echo "     - Restart service: sudo systemctl restart tokamak-ai-api"
echo ""
