# cleanup-drive-c-v2.ps1 - migrate C:\Users\PHONGQK app-data bloat to D:
# User granted full move/delete rights (Edit prompt.txt).
# Run: powershell -ExecutionPolicy Bypass -File scripts\cleanup-drive-c-v2.ps1

$ErrorActionPreference = "Continue"
function Report($msg) { Write-Host $msg }
Report ("=== START: C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")

# ------------------------------------------------------------------ #
# PART A - MOVE live app-data dirs to D: + create junction (no admin)
#   (these belong to tools still installed: codex, gemini, qwen,
#    AI caches, bun runtime)
# ------------------------------------------------------------------ #
$moves = @(
    @{ Name = ".codex";  Src = "C:\Users\PHONGQK\.codex";  Dst = "D:\dev\appdata\.codex" },
    @{ Name = ".gemini"; Src = "C:\Users\PHONGQK\.gemini"; Dst = "D:\dev\appdata\.gemini" },
    @{ Name = ".qwen";   Src = "C:\Users\PHONGQK\.qwen";   Dst = "D:\dev\appdata\.qwen" },
    @{ Name = ".cache";  Src = "C:\Users\PHONGQK\.cache";  Dst = "D:\dev\appdata\.cache" },
    @{ Name = ".bun";    Src = "C:\Users\PHONGQK\.bun";    Dst = "D:\dev\appdata\.bun" }
)

foreach ($m in $moves) {
    if (-not (Test-Path $m.Src)) { Report ("SKIP (missing): " + $m.Name); continue }
    try {
        New-Item -ItemType Directory -Path $m.Dst -Force | Out-Null
        robocopy $m.Src $m.Dst /E /MOVE /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
        if (Test-Path $m.Src) {
            # robocopy may leave empty root; clean it so junction can be made
            Remove-Item $m.Src -Recurse -Force -ErrorAction SilentlyContinue
        }
        # Junction requires the source path to not exist
        cmd /c mklink /J "$($m.Src)" "$($m.Dst)" | Out-Null
        if (Test-Path $m.Src) { Report ("MOVED+JUNCTION: " + $m.Name + " -> " + $m.Dst) }
        else { Report ("MOVED (junction failed): " + $m.Name) }
    } catch { Report ("ERROR moving " + $m.Name + " : " + $_.Exception.Message) }
}

# bun PATH update (user env) so `bun` still resolves after move
$bunBin = "D:\dev\appdata\.bun\bin"
if (Test-Path $bunBin) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -and -not ($userPath -like "*$bunBin*")) {
        [Environment]::SetEnvironmentVariable("Path", $userPath + ";" + $bunBin, "User")
        Report "PATH updated: added $bunBin (user env)"
    } elseif (-not $userPath) {
        [Environment]::SetEnvironmentVariable("Path", $bunBin, "User")
        Report "PATH updated: set $bunBin (user env)"
    }
}

# ------------------------------------------------------------------ #
# PART B - DELETE pure caches (installed tool no longer present)
# ------------------------------------------------------------------ #
$deletes = @(
    "C:\Users\PHONGQK\.gradle",
    "C:\Users\PHONGQK\AppData\Local\uv",
    "C:\Users\PHONGQK\AppData\Roaming\uv",
    "C:\Users\PHONGQK\AppData\Local\ms-playwright",
    "C:\Users\PHONGQK\AppData\Local\electron-builder",
    "C:\Users\PHONGQK\AppData\Local\electron",
    "C:\Users\PHONGQK\AppData\Local\CrashDumps"
)
foreach ($p in $deletes) {
    if (-not (Test-Path $p)) { Report ("SKIP (missing): " + $p); continue }
    try {
        Remove-Item $p -Recurse -Force -ErrorAction Stop
        Report ("DELETED: " + $p)
    } catch { Report ("ERROR deleting " + $p + " : " + $_.Exception.Message) }
}

Report ("=== END: C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")
