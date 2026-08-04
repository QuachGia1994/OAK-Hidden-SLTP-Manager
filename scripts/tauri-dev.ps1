# tauri-dev.ps1 — run `npm run tauri dev` with the VS MSVC environment loaded.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/tauri-dev.ps1
$ErrorActionPreference = "Stop"

$env:CARGO_HOME = if (Test-Path "D:\dev\toolchains\cargo") { "D:\dev\toolchains\cargo" } else { "$env:USERPROFILE\.cargo" }
$env:RUSTUP_HOME = if (Test-Path "D:\dev\toolchains\rustup") { "D:\dev\toolchains\rustup" } else { "$env:USERPROFILE\.rustup" }
$env:Path = "$env:CARGO_HOME\bin;" + $env:Path

$targetDir = if (Test-Path "D:\dev") { "D:\dev\oak-target" } else { $null }
if ($targetDir) {
    $env:CARGO_TARGET_DIR = $targetDir
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    Write-Error "vcvars64.bat not found at $vcvars"
}

$desktop = Join-Path $PSScriptRoot "..\apps\desktop"
$cmd = "call `"$vcvars`" >nul 2>&1 && cd /d `"$desktop`" && npm run tauri dev"
Write-Host ">>> $cmd"
cmd /c $cmd
exit $LASTEXITCODE
