# cleanup-drive-c-v2-fix.ps1 - finish junctions for dirs left empty by v2
# Run: powershell -ExecutionPolicy Bypass -File scripts\cleanup-drive-c-v2-fix.ps1

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
    # Remove the now-empty leftover dir (content already on D:)
    try {
        Remove-Item $f.Src -Recurse -Force -ErrorAction Stop
        Report ("REMOVED leftover: " + $f.Name)
    } catch {
        Report ("ERROR removing leftover " + $f.Name + " (locked?): " + $_.Exception.Message)
        continue
    }
    # Create junction now that source path is free
    cmd /c mklink /J "$($f.Src)" "$($f.Dst)" | Out-Null
    $ok = (Get-Item $f.Src -Force -ErrorAction SilentlyContinue).Attributes -match "ReparsePoint"
    if ($ok) { Report ("JUNCTION OK: " + $f.Name + " -> " + $f.Dst) }
    else { Report ("JUNCTION FAILED: " + $f.Name) }
}

Report ("=== C: free = " + [math]::Round((Get-PSDrive C).Free/1GB, 1) + " GB ===")
