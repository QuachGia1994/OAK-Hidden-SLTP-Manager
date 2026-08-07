@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [CHECK] Starting OAK Tauri desktop (dev)...
echo ==========================================

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Cannot detect 'npm' command. Install Node.js first.
    pause
    exit /b
)

if not exist "scripts\tauri-dev.ps1" (
    echo [ERROR] scripts\tauri-dev.ps1 not found.
    pause
    exit /b
)

if not exist "apps\desktop\node_modules" (
    echo [INFO] Installing desktop dependencies once...
    pushd apps\desktop
    call npm install
    popd
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed.
        pause
        exit /b
    )
)

echo [INFO] First run compiles Rust and can take several minutes.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tauri-dev.ps1"
if %errorlevel% neq 0 (
    echo [ERROR] Tauri dev exited with an error.
    pause
    exit /b
)
exit
