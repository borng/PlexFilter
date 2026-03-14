#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== PlexFilter + PlexAutoSkip Installer ==="
echo ""

# ── System dependencies ─────────────────────────────────────────────────

echo "[1/6] Checking system dependencies..."

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "ERROR: Python 3 is required. Install it first:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  macOS: brew install python3"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "  Python: $($PYTHON --version)"

if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "WARNING: ffmpeg not found. Local nudity detection requires it."
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  Windows: choco install ffmpeg  (or https://ffmpeg.org/download.html)"
    echo ""
fi

if ! command -v git &>/dev/null; then
    echo "ERROR: git is required."
    exit 1
fi

# ── PlexFilter backend ──────────────────────────────────────────────────

echo "[2/6] Installing PlexFilter backend dependencies..."
pip install -r backend/requirements.txt

# ── PlexFilter frontend ─────────────────────────────────────────────────

echo "[3/6] Building PlexFilter frontend..."
if [ -d frontend ] && command -v npm &>/dev/null; then
    cd frontend
    npm install
    npm run build
    rm -rf ../backend/static
    cp -r dist/ ../backend/static/
    cd ..
    echo "  Frontend built → backend/static/"
else
    echo "  Skipped (npm not found or no frontend/ dir). Install Node.js to build the UI."
fi

# ── Environment config ──────────────────────────────────────────────────

echo "[4/6] Setting up configuration..."
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "  Created backend/.env from template."
    echo "  >>> Edit backend/.env and set PLEXFILTER_PLEX_TOKEN <<<"
else
    echo "  backend/.env already exists, skipping."
fi

# ── PlexAutoSkip ─────────────────────────────────────────────────────────

echo "[5/6] Installing PlexAutoSkip..."
PAS_DIR="plexautoskip"

if [ -d "$PAS_DIR" ]; then
    echo "  $PAS_DIR/ already exists, pulling latest..."
    cd "$PAS_DIR"
    git pull --ff-only || true
    cd ..
else
    git clone https://github.com/mdhiggins/PlexAutoSkip.git "$PAS_DIR"
fi

pip install -r "$PAS_DIR/setup/requirements.txt"

# Generate default config if needed
if [ ! -f "$PAS_DIR/config/config.ini" ]; then
    mkdir -p "$PAS_DIR/config"
    cat > "$PAS_DIR/config/config.ini" << 'INICFG'
[Plex.tv]
# Your Plex authentication token (same one used in PlexFilter)
token =

[Server]
# Plex server address (hostname or IP, no http://)
address = localhost
port = 32400
ssl = False

[Security]
ignore-certs = False

[Custom]
# Path to PlexFilter's generated custom.json
# Adjust this to match your PLEXFILTER_PLEXAUTOSKIP_JSON_PATH
path = ../backend/custom.json
INICFG
    echo "  Created $PAS_DIR/config/config.ini"
    echo "  >>> Edit $PAS_DIR/config/config.ini and set your Plex token <<<"
else
    echo "  $PAS_DIR/config/config.ini already exists, skipping."
fi

# ── Summary ──────────────────────────────────────────────────────────────

echo "[6/6] Done!"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Before first run, edit these files:"
echo "  1. backend/.env              → set PLEXFILTER_PLEX_TOKEN"
echo "  2. $PAS_DIR/config/config.ini → set token under [Plex.tv]"
echo ""
echo "To start PlexFilter:"
echo "  ./start.sh"
echo "  Then open http://localhost:8000"
echo "  Scan library → Sync → Create profile → Generate custom.json"
echo ""
echo "To start PlexAutoSkip (watches playback and skips/mutes):"
echo "  cd $PAS_DIR && python main.py"
echo ""
echo "Both must be running for live skip/mute during Plex playback."
