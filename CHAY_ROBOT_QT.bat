@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [CHECK] Starting OAK Native Qt shell...
echo ==========================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Cannot detect 'python' command.
    pause
    exit /b
)

if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creating new virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot create virtual environment.
        pause
        exit /b
    )
)

echo [INFO] Checking Native Qt...
".\venv\Scripts\python.exe" -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Native Qt libraries once...
    ".\venv\Scripts\python.exe" -m pip install -r requirements_qt.txt --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot install Native Qt requirements.
        pause
        exit /b
    )
)
if %errorlevel% equ 0 (
    echo [OK] Native Qt ready.
)

start "" ".\venv\Scripts\pythonw.exe" "oak_qt_shell.py"
echo [OK] Native Qt shell started.
timeout /t 3 >nul
exit
