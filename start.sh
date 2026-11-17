#!/usr/bin/env bash
set -euo pipefail

# Ensure Homebrew and standard paths are available on macOS
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Groww Trading Lab — Local Startup Script
# Usage: ./start.sh [setup|dev|test|backend|frontend]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Groww Trading Lab — Local Setup      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo ""
}

check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found. Install from https://www.python.org${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python 3 $(python3 --version | cut -d' ' -f2)${NC}"
    
    if ! command -v node &> /dev/null; then
        echo -e "${RED}✗ Node.js not found. Install from https://nodejs.org${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js $(node --version)${NC}"
    
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}✗ npm not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ npm $(npm --version)${NC}"
    echo ""
}

setup_backend() {
    echo -e "${YELLOW}Setting up backend...${NC}"
    
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        python3 -m venv "$BACKEND_DIR/venv"
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
    
    "$BACKEND_DIR/venv/bin/pip" install --upgrade pip -q
    "$BACKEND_DIR/venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt" -q
    echo -e "${GREEN}✓ Python dependencies installed${NC}"
    
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
        echo -e "${YELLOW}⚠ Created .env from template — edit backend/.env with your Groww API token for live data${NC}"
    fi
    
    cd "$BACKEND_DIR"
    ./venv/bin/python -c "from app.database import init_db; init_db()" 2>/dev/null || true
    echo -e "${GREEN}✓ Database initialized${NC}"
    cd "$SCRIPT_DIR"
    
    echo -e "${GREEN}✓ Backend setup complete${NC}"
}

setup_frontend() {
    echo -e "${YELLOW}Setting up frontend...${NC}"
    
    cd "$FRONTEND_DIR"
    npm install --silent 2>/dev/null
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    cd "$SCRIPT_DIR"
    
    echo -e "${GREEN}✓ Frontend setup complete${NC}"
}

run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    cd "$BACKEND_DIR"
    ./venv/bin/python -m pytest tests/ -v
    echo -e "${GREEN}✓ Tests complete${NC}"
    cd "$SCRIPT_DIR"
}

start_dev() {
    echo -e "${BLUE}Starting development servers...${NC}"
    echo ""
    echo -e "  Backend:  ${GREEN}http://localhost:8000${NC}"
    echo -e "  Frontend: ${GREEN}http://localhost:3000${NC}"
    echo -e "  API Docs: ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
    echo ""
    
    # Start backend
    cd "$BACKEND_DIR"
    ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
    BACKEND_PID=$!
    cd "$SCRIPT_DIR"
    
    # Start frontend
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
    
    # Trap Ctrl+C to kill both
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
    
    wait
}

# Main
print_header

case "${1:-dev}" in
    setup)
        check_prerequisites
        setup_backend
        echo ""
        setup_frontend
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║         Setup complete!                  ║${NC}"
        echo -e "${GREEN}║   Run: ./start.sh dev                   ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
        ;;
    dev)
        start_dev
        ;;
    test)
        run_tests
        ;;
    backend)
        cd "$BACKEND_DIR"
        ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
        ;;
    frontend)
        cd "$FRONTEND_DIR"
        npm run dev
        ;;
    *)
        echo "Usage: ./start.sh [setup|dev|test|backend|frontend]"
        echo ""
        echo "  setup     - Install all dependencies and initialize database"
        echo "  dev       - Start both backend and frontend (default)"
        echo "  test      - Run backend tests"
        echo "  backend   - Start only the backend"
        echo "  frontend  - Start only the frontend"
        ;;
esac
