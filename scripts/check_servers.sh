#!/bin/bash

# Script to diagnose Ollama server connectivity issues

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Ollama Server Diagnostic Tool         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Read OLLAMA_SERVERS from .env
OLLAMA_SERVERS=$(grep "^OLLAMA_SERVERS=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$OLLAMA_SERVERS" ]; then
    echo -e "${RED}Error: OLLAMA_SERVERS not found in .env${NC}"
    exit 1
fi

echo -e "${GREEN}Found OLLAMA_SERVERS: $OLLAMA_SERVERS${NC}"
echo ""

# Split by comma
IFS=',' read -ra SERVERS <<< "$OLLAMA_SERVERS"

echo -e "${YELLOW}Testing each server...${NC}"
echo ""

for i in "${!SERVERS[@]}"; do
    SERVER="${SERVERS[$i]}"
    SERVER=$(echo "$SERVER" | xargs)  # Trim whitespace
    
    echo -e "${BLUE}Server $((i+1)): $SERVER${NC}"
    
    # Test 1: Basic connectivity
    echo -n "  Connectivity: "
    if curl -s --max-time 5 "$SERVER/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo -e "    ${YELLOW}Check if server is running and accessible${NC}"
        continue
    fi
    
    # Test 2: Get models
    echo -n "  Models: "
    MODELS_RESPONSE=$(curl -s --max-time 10 "$SERVER/api/tags" 2>&1)
    if [ $? -eq 0 ]; then
        MODEL_COUNT=$(echo "$MODELS_RESPONSE" | grep -o '"name"' | wc -l | tr -d ' ')
        if [ "$MODEL_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✓ $MODEL_COUNT models found${NC}"
            
            # Show first few model names
            MODEL_NAMES=$(echo "$MODELS_RESPONSE" | grep -o '"name":"[^"]*"' | head -3 | sed 's/"name":"\([^"]*\)"/\1/' | tr '\n' ', ' | sed 's/,$//')
            if [ -n "$MODEL_NAMES" ]; then
                echo -e "    ${YELLOW}Models: $MODEL_NAMES${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ No models found${NC}"
        fi
    else
        echo -e "${RED}✗ Failed to get models${NC}"
        echo -e "    ${YELLOW}Error: $MODELS_RESPONSE${NC}"
    fi
    
    # Test 3: Response time
    echo -n "  Response time: "
    START_TIME=$(date +%s%N)
    curl -s --max-time 10 "$SERVER/api/tags" > /dev/null 2>&1
    END_TIME=$(date +%s%N)
    DURATION=$(( (END_TIME - START_TIME) / 1000000 ))
    if [ "$DURATION" -lt 1000 ]; then
        echo -e "${GREEN}${DURATION}ms${NC}"
    elif [ "$DURATION" -lt 5000 ]; then
        echo -e "${YELLOW}${DURATION}ms${NC}"
    else
        echo -e "${RED}${DURATION}ms (slow)${NC}"
    fi
    
    echo ""
done

# Check API server status if running
echo -e "${YELLOW}Checking API server status...${NC}"

if command -v docker &> /dev/null && docker compose ps 2>/dev/null | grep -q "tokamak-ai-api.*Up"; then
    echo -e "${GREEN}Docker container is running${NC}"
    echo ""
    echo "Testing API server /status endpoint..."
    STATUS_RESPONSE=$(curl -s --max-time 5 "http://localhost:8000/status" -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env 2>/dev/null | cut -d'=' -f2- || echo '')" 2>&1)
    if [ $? -eq 0 ]; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
    else
        echo -e "${YELLOW}Could not reach API server /status endpoint${NC}"
    fi
elif systemctl is-active --quiet tokamak-ai-api 2>/dev/null; then
    echo -e "${GREEN}Systemd service is running${NC}"
    echo ""
    echo "Testing API server /status endpoint..."
    STATUS_RESPONSE=$(curl -s --max-time 5 "http://localhost:8000/status" -H "Authorization: Bearer $(grep '^ADMIN_API_KEY=' .env 2>/dev/null | cut -d'=' -f2- || echo '')" 2>&1)
    if [ $? -eq 0 ]; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
    else
        echo -e "${YELLOW}Could not reach API server /status endpoint${NC}"
    fi
else
    echo -e "${YELLOW}API server is not running${NC}"
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Diagnostic Complete                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
