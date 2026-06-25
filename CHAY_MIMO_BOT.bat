@echo off
chcp 65001 >nul
title MiMo Bridge Bot + Worker
cd /d "%~dp0"

echo ========================================
echo   MiMo Bridge Bot - Starting
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

python -c "import telebot" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing pyTelegramBotAPI...
    pip install pyTelegramBotAPI
)

echo [1/2] Starting MiMo Worker...
start "MiMo Worker" cmd /c "python mimo_worker.py"

timeout /t 1 /nobreak >nul

echo [2/2] Starting Telegram Bot...
start "MiMo Telegram Bot" cmd /c "python mimo_bot.py"

echo.
echo [DONE] Started! Press Ctrl+C to stop.
timeout /t 3 >nul
exit