#!/bin/bash
set -e

cd ~/Desktop/TaxFlow-Pro
source venv/bin/activate
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
=======

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
BACKEND_PID_FILE="$PROJECT_DIR/.backend.pid"
LOG_FILE="$PROJECT_DIR/logs/startup.log"

mkdir -p "$PROJECT_DIR/logs"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}=========================================="
echo -e "  TaxFlow Pro v3.7 — Starting Services"
echo -e "==========================================${NC}"
echo ""

echo -e "→ Checking Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo -e "  ${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ ! -f "$VENV_DIR/.requirements-installed" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.requirements-installed" ]; then
    echo -e "→ Installing Python dependencies..."
    pip install -q -r "$PROJECT_DIR/requirements.txt"
    touch "$VENV_DIR/.requirements-installed"
fi

echo -e "→ Checking Node environment..."
if [ ! -d "$PROJECT_DIR/node_modules" ]; then
    echo -e "  ${YELLOW}Installing npm dependencies...${NC}"
    cd "$PROJECT_DIR"
    npm install
fi

echo -e "→ Starting backend server..."
cd "$PROJECT_DIR"

if [ -f "$BACKEND_PID_FILE" ]; then
    kill -9 $(cat "$BACKEND_PID_FILE") 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
fi

rm -f backend/api_db.json
rm -rf backend/uploads backend/output 2>/dev/null || true
# Keep logs directory; backend uses it.

"$VENV_DIR/bin/uvicorn" backend.api:app --reload --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$BACKEND_PID_FILE"

echo -e "→ Waiting for backend health check..."
for i in {1..30}; do
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q '"status":"ok"'; then
        echo -e "  ${GREEN}✓ Backend ready at http://localhost:8000${NC}"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "  ${RED}✗ Backend failed to start. Check logs/startup.log${NC}"
        exit 1
    fi
done

echo -e "→ Starting frontend server..."
echo -e "${YELLOW}=========================================="
echo -e "  BOTH SERVERS RUNNING"
echo -e "==========================================${NC}"
echo -e "  ${GREEN}Backend:${NC}  http://localhost:8000"
echo -e "  ${GREEN}Frontend:${NC} http://localhost:5173"
echo -e "  ${GREEN}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop both servers."
echo ""

cleanup() {
    echo ""
    echo -e "${YELLOW}→ Shutting down backend...${NC}"
    if [ -f "$BACKEND_PID_FILE" ]; then
        kill -9 $(cat "$BACKEND_PID_FILE") 2>/dev/null || true
        rm -f "$BACKEND_PID_FILE"
    fi
    echo -e "${GREEN}✓ All services stopped.${NC}"
    exit 0
}
trap cleanup INT TERM EXIT

cd "$PROJECT_DIR"
npm run dev
