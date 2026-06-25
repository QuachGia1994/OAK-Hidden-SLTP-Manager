@echo off
chcp 65001 >nul
title MT4-MT5 Signal System
cd /d "%~dp0"

echo ==========================================
echo   MT4-MT5 Signal System - Starting
echo ==========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    timeout /t 3 >nul
    exit /b 1
)

python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Flask...
    pip install Flask
)
python -c "import MetaTrader5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing MetaTrader5...
    pip install MetaTrader5
)
python -c "import telebot" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing pyTelegramBotAPI...
    pip install pyTelegramBotAPI
)

echo [1/3] Starting MT4-MT5 Server...
start "MT4-MT5 Server" cmd /c "python mt4_mt5_server.py"

timeout /t 2 /nobreak >nul

echo [2/3] Starting MT5 Signal Bot...
start "MT5 Signal Bot" cmd /c "python mt5_signal_bot.py"

timeout /t 1 /nobreak >nul

echo [3/3] Starting MiMo Worker...
start "MiMo Worker" cmd /c "python mimo_worker.py"

echo.
echo [DONE] All started. Window closes in 3s...
timeout /t 3 >nul
exit