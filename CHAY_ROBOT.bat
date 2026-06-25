@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [CHECK] Starting...
echo ==========================================

:: 1. Check Python
echo [1/3] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Cannot detect 'python' command.
    echo Please restart computer to update PATH.
    pause
    exit /b
)
echo [OK] Python found.

:: 2. Check venv
echo [2/3] Checking virtual environment (venv)...
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creating new virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot create virtual environment.
        echo Please delete 'venv' folder and try again.
        pause
        exit /b
    )
)

:: 3. Install libraries
echo [3/3] Checking libraries (requirements.txt)...
".\venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [INFO] Installing libraries manually...
    ".\venv\Scripts\python.exe" -m pip install customtkinter MetaTrader5 --quiet
)

:: 4. Run app
echo ==========================================
echo [OK] Starting Robot...
echo ==========================================
start "" ".\venv\Scripts\pythonw.exe" "OAK_Hidden_SLTP_Manager.py"

echo [INFO] Robot started in background.
echo This window closes in 5 seconds.
timeout /t 5 >nul
exit