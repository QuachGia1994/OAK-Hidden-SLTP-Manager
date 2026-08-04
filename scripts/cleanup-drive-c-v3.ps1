# cleanup-drive-c-v3.ps1 - finalize junctions AFTER closing codex/gemini/opencode
# Run this AFTER closing: Codex CLI, Gemini/Antigravity IDE, and OpenCode.
#   powershell -ExecutionPolicy Bypass -File scripts\cleanup-drive-c-v3.ps1

$ErrorActionPreference = "Continue"
function Report($msg) { Write-Host $msg }

$fixes = @(
    @{ Name = ".codex";  Src = "C:\Users\PHONGQK\.codex";  Dst = "D:\dev\appdata\.codex" },
    @{ Name = ".gemini"; Src = "C:\Users\PHONGQK\.gemini"; Dst = "D:\dev\appdata\.gemini" },
    @{ Name = ".bun";    Src = "C:\Users\PHONGQK\.bun";    Dst = "D:\dev\appdata\.bun" }
)

foreach ($f in $fixes) {
    $isJunction = (Get-Item $f.Src -Force -ErrorAction SilentlyContinue).Attributes -match "ReparsePoint"
    if ($isJunction) { Report ("OK already junction: " + $f.Name); continue }
    # Merge any leftover files into D: then remove the source dir
    robocopy $f.Src $f.Dst /E /MOVE /NFL /NDL /NJH /NJS /R:0 /W:0 | Out-Null
    try {
        Remove-Item $f.Src -Recurse -Force -ErrorAction Stop
        cmd /c mklink /J "$($f.Src)" "$($f.Dst)" | Out-Null
        $ok = (Get-Item $f.Src -Force -ErrorAction SilentlyContinue).Attributes -match "ReparsePoint"
        if ($ok) { Report ("JUNCTION OK: " + $f.Name) }
        else { Report ("JUNCTION FAILED (retry after closing apps): " + $f.Name) }
    } catch {
        Report ("STILL LOCKED (close apps then rerun): " + $f.Name + " : " + $_.Exception.Message)
    }
}

Report ("=== C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")
