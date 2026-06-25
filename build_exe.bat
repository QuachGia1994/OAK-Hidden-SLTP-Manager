@echo off
cd /d "%~dp0"
echo Dang build file EXE ...
python build_exe.py
echo.
echo Build xong. Cua so se tu dong dong sau 3 giay...
timeout /t 3 >nul
exit
