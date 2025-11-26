#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.dashboard-venv"
DEPS_SENTINEL="$VENV_DIR/.deps_installed"

log() {
    echo "[TenderAI] $1"
}

log "Preparing Tender Vendor AI Dashboard (macOS)"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    log "Python 3.10+ is required. Install it from https://www.python.org/downloads/"
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; import platform; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
    log "Python 3.10+ is required. Current version: $($PYTHON_BIN --version 2>&1)"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    log "Missing .env file with API keys. Please add it and rerun the script."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    log "Creating isolated environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

if [ ! -f "$DEPS_SENTINEL" ]; then
    log "Installing dashboard dependencies (one-time step)"
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install --upgrade -e "$PROJECT_DIR"
    touch "$DEPS_SENTINEL"
else
    log "Dependencies already installed. Skipping."
fi

log "Starting dashboard → http://localhost:8501"
exec python -m streamlit run src/vendor_ai_agent/dashboard.py
