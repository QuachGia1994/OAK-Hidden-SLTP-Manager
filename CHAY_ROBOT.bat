@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo [KIEM TRA HE THONG] Dang bat dau...
echo ==========================================

:: 1. Kiem tra Python (Ban vua cai tu Windows Store)
echo [1/3] Dang kiem tra Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Van khong nhan dien duoc lenh 'python'.
    echo Vui long thu khoi dong lai may tinh de Windows cap nhat PATH.
    pause
    exit /b
)
echo [OK] Da tim thay Python.

:: 2. Tao/Kiem tra moi truong ao (venv)
echo [2/3] Dang kiem tra moi truong ao (venv)...
if not exist "venv\Scripts\python.exe" (
    echo [HE THONG] Dang khoi tao moi truong ao moi...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [LOI] Khong the tao moi truong ao. 
        echo Vui long thu xoa thu muc 'venv' neu no dang bi loi va chay lai file nay.
        pause
        exit /b
    )
)

:: 3. Cai dat thu vien
echo [3/3] Dang kiem tra thu vien (requirements.txt)...
".\venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [THONG BAO] Dang cai dat thu vien thu cong...
    ".\venv\Scripts\python.exe" -m pip install customtkinter MetaTrader5 --quiet
)

:: 4. Chay ung dung
echo ==========================================
echo [THANH CONG] Dang mo Robot...
echo ==========================================
:: Su dung pythonw.exe de an cua so đen
start "" ".\venv\Scripts\pythonw.exe" "OAK_Hidden_SLTP_Manager.py"

echo [HE THONG] Robot dang duoc khoi dong ngam.
echo Cua so nay se tu dong dong sau 5 giay.
timeout /t 5 >nul
exit
