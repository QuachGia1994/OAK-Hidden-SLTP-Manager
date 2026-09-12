@echo off
setlocal EnableExtensions
set "NO_PAUSE=0"
if /I "%~1"=="/nopause" set "NO_PAUSE=1"

cd /d "%~dp0"
title OAK Local H1 Scanner Setup

set "TASK_NAME=OAK Local H1 Scanner"
set "INSTALLER=%~dp0local-failover\install-local-h1-scanner-task.ps1"
set "CONFIG=%LOCALAPPDATA%\OAK Gatekeeper\telegram-failover-config.json"

echo.
echo ==========================================
echo   OAK Local H1 Scanner - One Click Setup
echo ==========================================
echo Repo: %~dp0
echo.

if not exist "%INSTALLER%" goto :missing_installer
where powershell.exe >nul 2>&1 || goto :missing_powershell
where node.exe >nul 2>&1 || goto :missing_node
where python.exe >nul 2>&1 || goto :missing_python
python.exe -c "import MetaTrader5" >nul 2>&1 || goto :missing_mt5
if not exist "%CONFIG%" goto :missing_config

echo [1/4] Doctor / prerequisite check...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER%" -Action Doctor
if errorlevel 1 goto :failed

echo.
echo [2/4] Install or repair Scheduled Task...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER%" -Action Install
if errorlevel 1 goto :failed

echo.
echo [3/4] Enable and start scanner now...
schtasks.exe /Change /TN "%TASK_NAME%" /ENABLE >nul 2>&1
if errorlevel 1 goto :failed
schtasks.exe /Run /TN "%TASK_NAME%" >nul 2>&1
if errorlevel 1 goto :failed

timeout /t 2 /nobreak >nul

echo.
echo [4/4] Current status...
schtasks.exe /Query /TN "%TASK_NAME%" /V /FO LIST
if errorlevel 1 goto :failed

echo.
echo SUCCESS: %TASK_NAME% is installed, enabled and started.
echo It will run at logon and repeat every 1 minute.
goto :done

:missing_installer
echo ERROR: Installer not found:
echo   %INSTALLER%
goto :failed

:missing_powershell
echo ERROR: Windows PowerShell is unavailable.
goto :failed

:missing_node
echo ERROR: Node.js is not installed or not in PATH.
goto :failed

:missing_python
echo ERROR: Python is not installed or not in PATH.
goto :failed

:missing_mt5
echo ERROR: Python package MetaTrader5 is missing.
echo Install it with: python -m pip install MetaTrader5
goto :failed

:missing_config
echo ERROR: Local OAK config is missing:
echo   %CONFIG%
echo.
echo On a new PC, first restore/bootstrap the protected OAK local config.
echo If dashboard\.env.local is configured, use:
echo   node .\local-failover\bootstrap-local-failover.mjs --local-primary
goto :failed

:failed
echo.
echo H1 Scanner setup FAILED. No success state is assumed.
if "%NO_PAUSE%"=="0" pause
exit /b 1

:done
if "%NO_PAUSE%"=="0" pause
exit /b 0
