@echo off
chcp 65001 >nul
title MT4-MT5 Dual Signal Server
echo.
echo ==========================================
echo   MT4-MT5 Dual Signal Server
echo   POST http://localhost:5000/mt4_data
echo ==========================================
echo.
echo Kiểm tra thư viện...
python -c "import flask; print('[OK] Flask:', flask.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Flask chưa cài. Đang cài...
    python -m pip install Flask
)
python -c "import MetaTrader5; print('[OK] MetaTrader5: installed')" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] MetaTrader5 chưa cài. Đang cài...
    python -m pip install MetaTrader5
)
echo.
echo ==========================================
echo   Đang khởi động server...
echo   Ctrl+C để dừng
echo ==========================================
echo.
python "%~dp0mt4_mt5_server.py"
echo.
echo Server đã dừng. Nhấn phím bất kỳ để thoát.
pause >nul
