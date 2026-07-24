# PowerShell script for automated Windows Task Scheduler EOD data updates
# Runs eod_collector update at 18:00 Mon-Fri

$ErrorActionPreference = "Stop"

# 1. Resolve project root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "[INFO] Local EOD Market Data Update starting in $ProjectRoot"

# 2. Activate virtual environment if available
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-Host "[INFO] Using virtual environment Python: $VenvPython"
    $PythonExe = $VenvPython
} else {
    Write-Host "[INFO] Virtual environment not found, using system python"
    $PythonExe = "python"
}

# 3. Run EOD update command
try {
    & $PythonExe -m eod_collector update
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -eq 0) {
        Write-Host "[SUCCESS] EOD Market Data update completed successfully." -ForegroundColor Green
        exit 0
    } else {
        Write-Error "[ERROR] EOD Collector update failed with exit code $ExitCode"
        exit $ExitCode
    }
} catch {
    Write-Error "[ERROR] Failed to execute EOD Collector update: $_"
    exit 1
}
