@echo off
chcp 65001 >nul
title MT4-MT5 Signal System
cd /d "%~dp0"

echo ==========================================
echo   MT4-MT5 Signal System - Khoi Dong
echo ==========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python chua duoc cai dat!
    timeout /t 3 >nul
    exit /b 1
)

python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Dang cai Flask...
    pip install Flask
)
python -c "import MetaTrader5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Dang cai MetaTrader5...
    pip install MetaTrader5
)
python -c "import telebot" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Dang cai pyTelegramBotAPI...
    pip install pyTelegramBotAPI
)

echo [1/3] Khoi dong MT4-MT5 Server...
start "MT4-MT5 Server" cmd /c "python mt4_mt5_server.py"

timeout /t 2 /nobreak >nul

echo [2/3] Khoi dong MT5 Signal Bot...
start "MT5 Signal Bot" cmd /c "python mt5_signal_bot.py"

timeout /t 1 /nobreak >nul

echo [3/3] Khoi dong MiMo Worker...
start "MiMo Worker" cmd /c "python mimo_worker.py"

echo.
echo [DONE] Tat ca da khoi dong. Cua so se tu dong dong...
timeout /t 3 >nul
exit
