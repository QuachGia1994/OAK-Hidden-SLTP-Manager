@echo off
chcp 65001 >nul
title MT4-MT5 Signal System
cd /d "%~dp0"

echo ==========================================
echo   MT4-MT5 Signal System - Khởi động
echo ==========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python chưa được cài đặt!
    timeout /t 3 >nul
    exit /b 1
)

python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Đang cài Flask...
    pip install Flask
)
python -c "import MetaTrader5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Đang cài MetaTrader5...
    pip install MetaTrader5
)
python -c "import telebot" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Đang cài pyTelegramBotAPI...
    pip install pyTelegramBotAPI
)

echo [1/3] Khởi động MT4-MT5 Server...
start "MT4-MT5 Server" cmd /c "python mt4_mt5_server.py"

timeout /t 2 /nobreak >nul

echo [2/3] Khởi động MT5 Signal Bot...
start "MT5 Signal Bot" cmd /c "python mt5_signal_bot.py"

timeout /t 1 /nobreak >nul

echo [3/3] Khởi động MiMo Worker...
start "MiMo Worker" cmd /c "python mimo_worker.py"

echo.
echo [DONE] Tất cả đã khởi động. Cửa sổ sẽ tự động đóng...
timeout /t 3 >nul
exit
