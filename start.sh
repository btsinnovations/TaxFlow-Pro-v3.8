#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
STANDALONE_DIR="$PROJECT_DIR/.python"
NODE_DIR="$PROJECT_DIR/.node"
BACKEND_PID_FILE="$PROJECT_DIR/.backend.pid"
LOG_FILE="$PROJECT_DIR/logs/startup.log"

mkdir -p "$PROJECT_DIR/logs"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helper: print colored messages
# ---------------------------------------------------------------------------
info() { echo -e "${BLUE}$1${NC}" >&2; }
warn() { echo -e "${YELLOW}$1${NC}" >&2; }
ok()   { echo -e "${GREEN}$1${NC}" >&2; }
err()  { echo -e "${RED}$1${NC}" >&2; }

# ---------------------------------------------------------------------------
# Helper: detect platform/architecture
# ---------------------------------------------------------------------------
detect_platform() {
    local os arch
    os=$(uname -s)
    arch=$(uname -m)
    case "$os" in
        Linux)
            case "$arch" in
                x86_64) echo "linux-x86_64" ;;
                aarch64|arm64) echo "linux-aarch64" ;;
                *) echo "unsupported" ;;
            esac
            ;;
        Darwin)
            case "$arch" in
                x86_64) echo "macos-x86_64" ;;
                arm64) echo "macos-arm64" ;;
                *) echo "unsupported" ;;
            esac
            ;;
        MINGW*|CYGWIN*|MSYS*)
            echo "windows"
            ;;
        *)
            echo "unsupported"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Helper: return the standalone Python download URL for this platform
# ---------------------------------------------------------------------------
standalone_python_url() {
    local platform="$1"
    # Astral python-build-standalone release used by the bootstrapper.
    # Update these values when you want to ship a newer Python version.
    local release_tag="20260610"
    local py_version="3.12.13"

    case "$platform" in
        linux-x86_64)
            echo "https://github.com/astral-sh/python-build-standalone/releases/download/${release_tag}/cpython-${py_version}%2B${release_tag}-x86_64-unknown-linux-gnu-install_only.tar.gz"
            ;;
        linux-aarch64)
            echo "https://github.com/astral-sh/python-build-standalone/releases/download/${release_tag}/cpython-${py_version}%2B${release_tag}-aarch64-unknown-linux-gnu-install_only.tar.gz"
            ;;
        macos-x86_64)
            echo "https://github.com/astral-sh/python-build-standalone/releases/download/${release_tag}/cpython-${py_version}%2B${release_tag}-x86_64-apple-darwin-install_only.tar.gz"
            ;;
        macos-arm64)
            echo "https://github.com/astral-sh/python-build-standalone/releases/download/${release_tag}/cpython-${py_version}%2B${release_tag}-aarch64-apple-darwin-install_only.tar.gz"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Helper: check whether a given python binary can create a venv
# ---------------------------------------------------------------------------
python_has_venv() {
    local py="$1"
    "$py" -m venv --help >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Helper: bootstrap a standalone Python when the system one lacks venv/pip
# ---------------------------------------------------------------------------
ensure_standalone_python() {
    local platform
    platform=$(detect_platform)

    if [ "$platform" = "unsupported" ]; then
        err "Unsupported platform: $(uname -s) $(uname -m)"
        err "Please install Python 3.10+ with venv support manually."
        exit 1
    fi

    if [ -f "$STANDALONE_DIR/bin/python3" ]; then
        info "Using previously downloaded standalone Python."
        echo "$STANDALONE_DIR/bin/python3"
        return 0
    fi

    local url
    url=$(standalone_python_url "$platform")
    if [ -z "$url" ]; then
        err "No standalone Python package available for $platform."
        err "Please install Python 3.10+ with venv support manually."
        exit 1
    fi

    warn "Your system Python does not support virtual environments."
    warn "Downloading a standalone Python for $platform (one-time, ~40 MB)..."
    mkdir -p "$STANDALONE_DIR"
    local tarball="$PROJECT_DIR/.python-bootstrap.tar.gz"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$tarball" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tarball" "$url"
    else
        err "This script needs curl or wget to download Python."
        exit 1
    fi

    info "Extracting standalone Python..."
    tar -xzf "$tarball" -C "$STANDALONE_DIR" --strip-components=1
    rm -f "$tarball"

    if [ ! -f "$STANDALONE_DIR/bin/python3" ]; then
        err "Standalone Python extraction failed."
        exit 1
    fi

    ok "Standalone Python ready."
    echo "$STANDALONE_DIR/bin/python3"
}

# ---------------------------------------------------------------------------
# Helper: pick a Python interpreter guaranteed to support venv
# ---------------------------------------------------------------------------
resolve_python() {
    # Prefer system python3 if it has venv support.
    if command -v python3 >/dev/null 2>&1 && python_has_venv "python3"; then
        echo "python3"
        return 0
    fi

    # Fall back to a standalone Python build.
    ensure_standalone_python
}

# ---------------------------------------------------------------------------
# Helper: return the standalone Node.js download URL for this platform
# ---------------------------------------------------------------------------
standalone_node_url() {
    local platform="$1"
    # Node.js LTS version used by the bootstrapper.
    # Update this value when you want to ship a newer Node version.
    local node_version="v20.19.0"

    case "$platform" in
        linux-x86_64)
            echo "https://nodejs.org/dist/${node_version}/node-${node_version}-linux-x64.tar.xz"
            ;;
        linux-aarch64)
            echo "https://nodejs.org/dist/${node_version}/node-${node_version}-linux-arm64.tar.xz"
            ;;
        macos-x86_64)
            echo "https://nodejs.org/dist/${node_version}/node-${node_version}-darwin-x64.tar.gz"
            ;;
        macos-arm64)
            echo "https://nodejs.org/dist/${node_version}/node-${node_version}-darwin-arm64.tar.gz"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Helper: bootstrap a standalone Node.js when the system one is missing
# ---------------------------------------------------------------------------
ensure_standalone_node() {
    local platform
    platform=$(detect_platform)

    if [ "$platform" = "unsupported" ]; then
        err "Unsupported platform: $(uname -s) $(uname -m)"
        err "Please install Node.js 18+ manually."
        exit 1
    fi

    if [ -f "$NODE_DIR/bin/node" ] && [ -f "$NODE_DIR/bin/npm" ]; then
        info "Using previously downloaded standalone Node.js."
        return 0
    fi

    local url
    url=$(standalone_node_url "$platform")
    if [ -z "$url" ]; then
        err "No standalone Node.js package available for $platform."
        err "Please install Node.js 18+ manually."
        exit 1
    fi

    warn "Node.js was not found on this system."
    warn "Downloading a standalone Node.js for $platform (one-time, ~50 MB)..."
    mkdir -p "$NODE_DIR"
    local tarball="$PROJECT_DIR/.node-bootstrap.tar.xz"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$tarball" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tarball" "$url"
    else
        err "This script needs curl or wget to download Node.js."
        exit 1
    fi

    info "Extracting standalone Node.js..."
    tar -xf "$tarball" -C "$NODE_DIR" --strip-components=1
    rm -f "$tarball"

    if [ ! -f "$NODE_DIR/bin/node" ] || [ ! -f "$NODE_DIR/bin/npm" ]; then
        err "Standalone Node.js extraction failed."
        exit 1
    fi

    ok "Standalone Node.js ready."
}

# ---------------------------------------------------------------------------
# Helper: pick Node/npm binaries
# ---------------------------------------------------------------------------
resolve_node() {
    # Prefer system Node if available.
    if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
        echo "$(command -v node)"
        return 0
    fi

    # Fall back to a standalone Node.js build.
    ensure_standalone_node
    echo "$NODE_DIR/bin/node"
}

# ---------------------------------------------------------------------------
# Load .env if present; otherwise auto-create from .env.example
# ---------------------------------------------------------------------------
if [ ! -f "$PROJECT_DIR/.env" ] && [ -f "$PROJECT_DIR/.env.example" ]; then
    info "Creating .env from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# ---------------------------------------------------------------------------
# Main startup
# ---------------------------------------------------------------------------
echo -e "${YELLOW}=========================================="
echo -e "  TaxFlow Pro v3.8 -- Starting Services"
echo -e "==========================================${NC}"
echo ""

PYTHON_CMD=$(resolve_python)
info "Using Python: $PYTHON_CMD"

info "Checking Python environment..."
if [ ! -d "$VENV_DIR" ]; then
    warn "  Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if [ ! -f "$VENV_DIR/.requirements-installed" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.requirements-installed" ]; then
    info "Installing Python dependencies..."
    pip install -q -r "$PROJECT_DIR/requirements.txt"
    touch "$VENV_DIR/.requirements-installed"
fi

NODE_BIN=$(resolve_node)
# Ensure standalone Node/npm are on PATH so npm scripts can find `node`.
if [ "$NODE_BIN" = "$NODE_DIR/bin/node" ]; then
    export PATH="$NODE_DIR/bin:$PATH"
    NPM_CMD="$NODE_DIR/bin/npm"
else
    NPM_CMD="$(command -v npm)"
fi
info "Using Node: $NODE_BIN"
info "Using npm:  $NPM_CMD"

info "Checking Node environment..."
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    warn "  Installing npm dependencies..."
    cd "$PROJECT_DIR/frontend"
    "$NPM_CMD" install
fi

info "Starting backend server..."
cd "$PROJECT_DIR"

if [ -f "$BACKEND_PID_FILE" ]; then
    OLD_PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null) || true
    if [ -n "$OLD_PID" ]; then
        kill "$OLD_PID" 2>/dev/null || true
    fi
    rm -f "$BACKEND_PID_FILE"
fi

# Keep any legacy JSON datastore out of the way without failing if absent.
rm -f backend/api_db.json 2>/dev/null || true
rm -rf backend/uploads backend/output 2>/dev/null || true

"$VENV_DIR/bin/uvicorn" backend.api:app --reload --reload-dir "$PROJECT_DIR/backend" --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$BACKEND_PID_FILE"

info "Waiting for backend health check..."
for i in {1..30}; do
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q '"status":"ok"'; then
        ok "  Backend ready at http://localhost:8000"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        err "  Backend failed to start. Check logs/startup.log"
        exit 1
    fi
done

info "Starting frontend server..."
echo -e "${YELLOW}=========================================="
echo -e "  BOTH SERVERS RUNNING"
echo -e "==========================================${NC}"
echo -e "  ${GREEN}Backend:${NC}  http://localhost:8000"
echo -e "  ${GREEN}Frontend:${NC} http://localhost:3000"
echo -e "  ${GREEN}API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop both servers."
echo ""

cleanup() {
    echo ""
    warn "Shutting down backend..."
    if [ -f "$BACKEND_PID_FILE" ]; then
        OLD_PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null) || true
        if [ -n "$OLD_PID" ]; then
            kill "$OLD_PID" 2>/dev/null || true
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    ok "All services stopped."
    exit 0
}
trap cleanup INT TERM EXIT

cd "$PROJECT_DIR/frontend"
"$NPM_CMD" run dev
