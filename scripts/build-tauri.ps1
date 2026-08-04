# build-tauri.ps1 — build the Tauri shell with the VS MSVC environment loaded.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build-tauri.ps1 [check|build|dev]
#
# Loads the VS Build Tools environment (link.exe etc.) then delegates to cargo.
param(
    [ValidateSet("check", "build", "dev", "clippy", "test")]
    [string]$Action = "check"
)

$ErrorActionPreference = "Stop"

# Rust lives on D: (see repo setup) — point cargo at it.
$env:CARGO_HOME = if (Test-Path "D:\dev\toolchains\cargo") { "D:\dev\toolchains\cargo" } else { "$env:USERPROFILE\.cargo" }
$env:RUSTUP_HOME = if (Test-Path "D:\dev\toolchains\rustup") { "D:\dev\toolchains\rustup" } else { "$env:USERPROFILE\.rustup" }
$env:Path = "$env:CARGO_HOME\bin;" + $env:Path

# Keep cargo's build artifacts off the small C: drive when D: is available.
$targetDir = if (Test-Path "D:\dev") { "D:\dev\oak-target" } else { $null }
if ($targetDir) {
    $env:CARGO_TARGET_DIR = $targetDir
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    Write-Error "vcvars64.bat not found at $vcvars"
}

$manifest = Join-Path $PSScriptRoot "..\apps\desktop\src-tauri\Cargo.toml"
$cmd = "call `"$vcvars`" >nul 2>&1 && cargo $Action --manifest-path `"$manifest`""
Write-Host ">>> $cmd"
cmd /c $cmd
exit $LASTEXITCODE
