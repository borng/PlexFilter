#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Check for .env
if [ ! -f backend/.env ]; then
    echo "No backend/.env found. Creating from .env.example..."
    cp backend/.env.example backend/.env
    echo "Edit backend/.env with your PLEXFILTER_PLEX_TOKEN before running again."
    exit 1
fi

# Install backend deps if needed
if ! python -c "import nudenet" 2>/dev/null; then
    echo "Installing backend dependencies..."
    pip install -r backend/requirements.txt
fi

# Build frontend if static dir doesn't exist
if [ ! -d backend/static ]; then
    if [ -d frontend ] && command -v npm &>/dev/null; then
        echo "Building frontend..."
        cd frontend
        npm install
        npm run build
        cp -r dist/ ../backend/static/
        cd ..
    else
        echo "Warning: No frontend build found at backend/static/"
        echo "  Run: cd frontend && npm install && npm run build && cp -r dist/ ../backend/static/"
    fi
fi

echo "Starting PlexFilter on http://localhost:8000"
cd backend
exec uvicorn plexfilter.main:app --host 0.0.0.0 --port 8000
