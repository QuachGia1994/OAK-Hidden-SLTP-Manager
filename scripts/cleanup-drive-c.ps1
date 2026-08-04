# cleanup-drive-c.ps1 - move/delete C: bloat to D: (user granted full rights)
# Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup-drive-c.ps1

$ErrorActionPreference = "Continue"

function Report($msg) { Write-Host $msg }

Report ("=== START: C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")

# 1. Delete VS installer Package Cache (safe - MSI cache only)
$pkgCache = "C:\ProgramData\Package Cache"
if (Test-Path $pkgCache) {
    try {
        Remove-Item $pkgCache -Recurse -Force -ErrorAction Stop
        Report "DELETED: $pkgCache"
    } catch { Report ("ERROR deleting $pkgCache : " + $_.Exception.Message) }
} else { Report "SKIP (missing): $pkgCache" }

# 2. Finish moving .rustup leftover -> D:\dev\toolchains\rustup
$rustupSrc = Join-Path $env:USERPROFILE ".rustup"
$rustupDst = "D:\dev\toolchains\rustup"
if (Test-Path $rustupSrc) {
    try {
        New-Item -ItemType Directory -Path $rustupDst -Force | Out-Null
        robocopy $rustupSrc $rustupDst /E /MOVE /NFL /NDL /NJH /NJS | Out-Null
        Report "MOVED: $rustupSrc -> $rustupDst"
    } catch { Report ("ERROR moving .rustup : " + $_.Exception.Message) }
} else { Report "SKIP (.rustup already moved)" }

# 3. Move npm cache -> D:\dev\npm-cache + reconfigure npm
$npmSrc = Join-Path $env:LOCALAPPDATA "npm-cache"
$npmDst = "D:\dev\npm-cache"
if (Test-Path $npmSrc) {
    try {
        New-Item -ItemType Directory -Path $npmDst -Force | Out-Null
        robocopy $npmSrc $npmDst /E /MOVE /NFL /NDL /NJH /NJS | Out-Null
        npm config set cache $npmDst --location=user 2>$null
        Report "MOVED npm-cache -> $npmDst + npm config set"
    } catch { Report ("ERROR moving npm-cache : " + $_.Exception.Message) }
} else { Report "SKIP (npm-cache missing)" }

# 4. Move pip cache -> D:\dev\pip-cache + set PIP_CACHE_DIR
$pipSrc = Join-Path $env:LOCALAPPDATA "pip"
$pipDst = "D:\dev\pip-cache"
if (Test-Path $pipSrc) {
    try {
        New-Item -ItemType Directory -Path $pipDst -Force | Out-Null
        robocopy $pipSrc $pipDst /E /MOVE /NFL /NDL /NJH /NJS | Out-Null
        [Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", $pipDst, "User")
        Report "MOVED pip cache -> $pipDst + PIP_CACHE_DIR set"
    } catch { Report ("ERROR moving pip : " + $_.Exception.Message) }
} else { Report "SKIP (pip cache missing)" }

# 5. Clean Temp (in-use files are skipped automatically)
$tempDir = $env:LOCALAPPDATA + "\Temp"
if (Test-Path $tempDir) {
    Get-ChildItem $tempDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop } catch { }
    }
    Report "CLEANED: $tempDir"
}

Report ("=== END: C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")
