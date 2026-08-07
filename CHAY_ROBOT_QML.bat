@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [CHECK] Starting OAK Manager QML shell...
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

echo [INFO] Checking PySide6...
".\venv\Scripts\python.exe" -c "from PySide6.QtQuickWidgets import QQuickWidget" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PySide6 libraries once...
    ".\venv\Scripts\python.exe" -m pip install -r requirements_qt.txt --quiet
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot install PySide6 requirements.
        pause
        exit /b
    )
)
if %errorlevel% equ 0 (
    echo [OK] PySide6 ready.
)

rem Force the Qt windowed platform: oak_qml_app.py defaults to
rem QT_QPA_PLATFORM=offscreen, which renders an invisible window.
set QT_QPA_PLATFORM=windows

start "" ".\venv\Scripts\pythonw.exe" "oak_qml_app.py"
echo [OK] OAK Manager QML shell started (Profiles + Dashboard live).
timeout /t 3 >nul
exit
