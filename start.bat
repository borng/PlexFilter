@echo off
setlocal

cd /d "%~dp0"

:: Check for .env
if not exist "backend\.env" (
    echo No backend\.env found. Creating from .env.example...
    copy "backend\.env.example" "backend\.env"
    echo Edit backend\.env with your PLEXFILTER_PLEX_TOKEN before running again.
    pause
    exit /b 1
)

:: Install backend deps if needed
python -c "import nudenet" 2>nul
if errorlevel 1 (
    echo Installing backend dependencies...
    pip install -r backend\requirements.txt
)

:: Build frontend if static dir doesn't exist
if not exist "backend\static" (
    if exist "frontend" (
        where npm >nul 2>nul
        if not errorlevel 1 (
            echo Building frontend...
            cd frontend
            call npm install
            call npm run build
            xcopy /e /i /y dist ..\backend\static
            cd ..
        ) else (
            echo Warning: No frontend build found at backend\static\
            echo   Run: cd frontend ^&^& npm install ^&^& npm run build ^&^& xcopy /e /i /y dist ..\backend\static
        )
    )
)

echo Starting PlexFilter on http://localhost:8000
cd backend
python -m uvicorn plexfilter.main:app --host 0.0.0.0 --port 8000
pause
