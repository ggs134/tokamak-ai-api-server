#!/bin/bash

# Tokamak AI API Server Deployment Script for Raspberry Pi 5
# Optimized for ARM64 architecture and limited resources

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Tokamak AI API Server (Raspberry Pi 5) ║${NC}"
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}Warning: This script is optimized for Raspberry Pi${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
    echo -e "${GREEN}Detected: $MODEL${NC}"
fi

# Check architecture
ARCH=$(uname -m)
echo -e "${GREEN}Architecture: $ARCH${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root${NC}"
   exit 1
fi

# Check available memory
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
echo -e "${GREEN}Total Memory: ${TOTAL_MEM}MB${NC}"

if [ "$TOTAL_MEM" -lt 2048 ]; then
    echo -e "${YELLOW}Warning: Low memory detected. Consider using swap space.${NC}"
fi

# Install system dependencies
echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev build-essential

# Optional: Install nginx if needed
read -p "Install Nginx reverse proxy? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo apt install -y nginx
    NGINX_INSTALLED=true
else
    NGINX_INSTALLED=false
fi

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
    
    echo "Copying application files..."
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
    echo -e "${GREEN}✓ Files copied${NC}"
else
    echo -e "${RED}Error: app directory not found. Run this script from the project root.${NC}"
    exit 1
fi

cd $APP_DIR

# Create data directory for SQLite
mkdir -p data

# Setup virtual environment
echo -e "${YELLOW}[3/6] Setting up Python virtual environment...${NC}"
if [ "$IS_UPDATE" = true ] && [ -d "venv" ]; then
    echo -e "${GREEN}Existing virtual environment found. Updating dependencies...${NC}"
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    echo "Updating dependencies (this may take a while on Raspberry Pi)..."
    pip install -r requirements.txt --upgrade
    echo -e "${GREEN}✓ Virtual environment updated${NC}"
else
    echo -e "${GREEN}Creating new virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip for better compatibility
    pip install --upgrade pip setuptools wheel
    
    # Install dependencies (may take longer on Raspberry Pi)
    echo "Installing dependencies (this may take a while on Raspberry Pi)..."
    pip install -r requirements.txt
    
    echo -e "${GREEN}✓ Virtual environment ready${NC}"
fi

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

# Determine optimal worker count based on CPU cores
CPU_CORES=$(nproc)
if [ "$CPU_CORES" -ge 4 ]; then
    WORKERS=2
elif [ "$CPU_CORES" -ge 2 ]; then
    WORKERS=1
else
    WORKERS=1
fi

echo -e "${GREEN}Detected $CPU_CORES CPU cores. Setting workers to $WORKERS${NC}"

# Update .env
sed -i "s|OLLAMA_SERVERS=.*|OLLAMA_SERVERS=$OLLAMA_SERVERS|" .env
sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
sed -i "s|DATABASE_URL=.*|DATABASE_URL=sqlite+aiosqlite:////$APP_DIR/data/tokamak_ai_api.db|" .env
# Ensure WORKERS is set in .env (add if not exists, update if exists)
if grep -q "^WORKERS=" .env; then
    sed -i "s|^WORKERS=.*|WORKERS=$WORKERS|" .env
else
    echo "WORKERS=$WORKERS" >> .env
fi

# Raspberry Pi optimization: Lower default rate limit if memory is limited
if [ "$TOTAL_MEM" -lt 4096 ]; then
    sed -i "s|DEFAULT_RATE_LIMIT=.*|DEFAULT_RATE_LIMIT=500|" .env
    echo -e "${YELLOW}Reduced default rate limit to 500 for low-memory system${NC}"
fi

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

# Create startup wrapper script
cat > $APP_DIR/start.sh << 'STARTEOF'
#!/bin/bash
set -e
cd "$(dirname "$0")"
source venv/bin/activate

# Load .env file if it exists (systemd EnvironmentFile also loads it, but this ensures it's available)
# systemd's EnvironmentFile handles comments automatically, but we load it here too for safety
if [ -f .env ]; then
    set -a
    # Source .env file (systemd will also load it via EnvironmentFile)
    . .env
    set +a
fi

# Use WORKERS from environment, default to 2 for Raspberry Pi
WORKERS=${WORKERS:-2}

# Validate WORKERS is a positive integer
if ! [[ "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: WORKERS must be a positive integer, got: $WORKERS" >&2
    WORKERS=2
fi

# Start uvicorn with configured workers
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers "$WORKERS"
STARTEOF
chmod +x $APP_DIR/start.sh

sudo tee /etc/systemd/system/tokamak-ai-api.service > /dev/null << EOF
[Unit]
Description=Tokamak AI API Server (Raspberry Pi)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
# Load environment variables from .env file
EnvironmentFile=$APP_DIR/.env
# Raspberry Pi optimization: Lower priority
Nice=10
# Memory limit (optional, adjust based on your Pi's RAM)
# For Pi 4 with 4GB RAM, consider: MemoryMax=2G
# For Pi 5 with 8GB RAM, consider: MemoryMax=4G
# MemoryMax=2G
# Use wrapper script that handles environment variables
ExecStart=$APP_DIR/start.sh
Restart=always
RestartSec=5
# Restart more frequently on Pi to handle memory issues
StartLimitInterval=300
StartLimitBurst=5
# Standard output and error logging
StandardOutput=journal
StandardError=journal

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

# Wait a moment for service to start
sleep 2

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Deployment Complete!                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "Service status: ${GREEN}$(sudo systemctl is-active tokamak-ai-api)${NC}"
echo -e "API endpoint: ${GREEN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
echo ""
echo "System Information:"
echo "  CPU Cores: $CPU_CORES"
echo "  Workers: $WORKERS"
echo "  Total Memory: ${TOTAL_MEM}MB"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status tokamak-ai-api    # Check status"
echo "  sudo systemctl restart tokamak-ai-api   # Restart service"
echo "  sudo journalctl -u tokamak-ai-api -f    # View logs"
echo "  sudo systemctl stop tokamak-ai-api       # Stop service"
echo ""
echo "Raspberry Pi Optimization Tips:"
echo "  1. Monitor temperature: vcgencmd measure_temp"
echo "  2. Check memory usage: free -h"
echo "  3. Consider adding swap if memory is limited"
echo "  4. Use active cooling for sustained loads"
echo ""
echo "Next steps:"
echo "  1. Configure firewall: sudo ufw allow 8000/tcp"
if [ "$NGINX_INSTALLED" = true ]; then
    echo "  2. Setup Nginx reverse proxy (optional)"
fi
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

