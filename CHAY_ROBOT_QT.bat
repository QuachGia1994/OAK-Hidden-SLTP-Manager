@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [CHECK] Starting OAK Native Qt shell...
echo ==========================================

where python >nul 2>&1
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
    goto :install_deps
)

echo [INFO] Checking Native Qt...
"%~dp0venv\Scripts\python.exe" -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if %errorlevel% neq 0 (
    :install_deps
    echo [INFO] Installing Native Qt libraries...
    "%~dp0venv\Scripts\python.exe" -m pip install -r requirements_qt.txt --quiet --disable-pip-version-check
    if %errorlevel% neq 0 (
        echo [ERROR] Cannot install Native Qt requirements.
        pause
        exit /b
    )
)

echo [OK] Native Qt ready.
start "" "%~dp0venv\Scripts\pythonw.exe" "oak_qt_shell.py"
echo [OK] Native Qt shell started.
exit
