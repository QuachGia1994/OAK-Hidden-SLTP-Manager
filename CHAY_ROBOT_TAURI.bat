@echo off
setlocal
cd /d "%~dp0robot-sltp-pro"
set "EXE=%CD%\src-tauri\target\release\robot-sltp-pro.exe"

echo ==========================================
echo   ROBOT SLTP Pro - Fast Launch
 echo ==========================================

if not exist "%EXE%" (
  echo [INFO] Release executable not found. Building once...
  call "%~dp0BUILD_ROBOT_TAURI.bat"
  if errorlevel 1 exit /b 1
)

if not exist "%EXE%" (
  echo [ERROR] Release executable is still missing.
  pause
  exit /b 1
)

start "ROBOT SLTP Pro" "%EXE%"
exit /b 0
