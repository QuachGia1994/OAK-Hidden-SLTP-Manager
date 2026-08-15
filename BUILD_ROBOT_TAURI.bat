@echo off
setlocal
cd /d "%~dp0robot-sltp-pro"
set "PATH=D:\Rust\.cargo\bin;%PATH%"
set "RUSTUP_HOME=D:\Rust\.rustup"
set "CARGO_HOME=D:\Rust\.cargo"
set "VSDEV=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if not exist "%VSDEV%" echo [ERROR] Visual Studio Build Tools not found.& pause & exit /b 1
call "%VSDEV%" -arch=x64
if errorlevel 1 goto :fail
if not exist "node_modules\.bin\tauri.cmd" (
  echo [INFO] Installing Tauri dependencies...
  call npm ci
  if errorlevel 1 goto :fail
)
call npm run tauri build
if errorlevel 1 goto :fail
echo [OK] Tauri release built.
exit /b 0
:fail
echo [ERROR] Release build failed.
pause
exit /b 1
