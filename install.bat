@echo off
setlocal

cd /d "%~dp0"

echo === PlexFilter + PlexAutoSkip Installer ===
echo.

:: ── System dependencies ─────────────────────────────────────────────────

echo [1/6] Checking system dependencies...

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3 is required. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: ffmpeg not found. Local nudity detection requires it.
    echo   Install: choco install ffmpeg  ^(or https://ffmpeg.org/download.html^)
    echo.
)

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: git is required. Install from https://git-scm.com/
    pause
    exit /b 1
)

:: ── PlexFilter backend ──────────────────────────────────────────────────

echo [2/6] Installing PlexFilter backend dependencies...
pip install -r backend\requirements.txt

:: ── PlexFilter frontend ─────────────────────────────────────────────────

echo [3/6] Building PlexFilter frontend...
if exist "frontend" (
    where npm >nul 2>nul
    if not errorlevel 1 (
        cd frontend
        call npm install
        call npm run build
        if exist "..\backend\static" rmdir /s /q "..\backend\static"
        xcopy /e /i /y dist ..\backend\static
        cd ..
        echo   Frontend built to backend\static\
    ) else (
        echo   Skipped ^(npm not found^). Install Node.js to build the UI.
    )
) else (
    echo   Skipped ^(no frontend\ dir^).
)

:: ── Environment config ──────────────────────────────────────────────────

echo [4/6] Setting up configuration...
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env"
    echo   Created backend\.env from template.
    echo   ^>^>^> Edit backend\.env and set PLEXFILTER_PLEX_TOKEN ^<^<^<
) else (
    echo   backend\.env already exists, skipping.
)

:: ── PlexAutoSkip ─────────────────────────────────────────────────────────

echo [5/6] Installing PlexAutoSkip...
set PAS_DIR=plexautoskip

if exist "%PAS_DIR%" (
    echo   %PAS_DIR%\ already exists, pulling latest...
    cd "%PAS_DIR%"
    git pull --ff-only
    cd ..
) else (
    git clone https://github.com/mdhiggins/PlexAutoSkip.git "%PAS_DIR%"
)

pip install -r "%PAS_DIR%\setup\requirements.txt"

if not exist "%PAS_DIR%\config\config.ini" (
    if not exist "%PAS_DIR%\config" mkdir "%PAS_DIR%\config"
    (
        echo [Plex.tv]
        echo # Your Plex authentication token ^(same one used in PlexFilter^)
        echo token =
        echo.
        echo [Server]
        echo # Plex server address ^(hostname or IP, no http://^)
        echo address = localhost
        echo port = 32400
        echo ssl = False
        echo.
        echo [Security]
        echo ignore-certs = False
        echo.
        echo [Custom]
        echo # Path to PlexFilter's generated custom.json
        echo path = ..\backend\custom.json
    ) > "%PAS_DIR%\config\config.ini"
    echo   Created %PAS_DIR%\config\config.ini
    echo   ^>^>^> Edit %PAS_DIR%\config\config.ini and set your Plex token ^<^<^<
) else (
    echo   %PAS_DIR%\config\config.ini already exists, skipping.
)

:: ── Summary ──────────────────────────────────────────────────────────────

echo [6/6] Done!
echo.
echo === Setup Complete ===
echo.
echo Before first run, edit these files:
echo   1. backend\.env                    - set PLEXFILTER_PLEX_TOKEN
echo   2. %PAS_DIR%\config\config.ini    - set token under [Plex.tv]
echo.
echo To start PlexFilter:
echo   start.bat
echo   Then open http://localhost:8000
echo   Scan library ^> Sync ^> Create profile ^> Generate custom.json
echo.
echo To start PlexAutoSkip ^(watches playback and skips/mutes^):
echo   cd %PAS_DIR% ^&^& python main.py
echo.
echo Both must be running for live skip/mute during Plex playback.
echo.
pause
