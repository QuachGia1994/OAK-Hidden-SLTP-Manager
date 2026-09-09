[CmdletBinding()]
param(
    [ValidateSet('Install','Status','Uninstall')]
    [string]$Action = 'Install',
    [switch]$DryRun,
    [switch]$NoDialog,
    [string]$SourceEx5 = '',
    [string]$ChecksumFile = ''
)

$ErrorActionPreference = 'Stop'
if (-not $SourceEx5) { $SourceEx5 = Join-Path $PSScriptRoot 'OAK_NeoTech_Compliance_EA.ex5' }
if (-not $ChecksumFile) { $ChecksumFile = Join-Path $PSScriptRoot 'OAK_NeoTech_Compliance_EA.sha256.txt' }
$EaName = 'OAK_NeoTech_Compliance_EA.ex5'

function Show-OakMessage {
    param([string]$Text, [string]$Title = 'OAK NeoTech C5', [ValidateSet('Info','Error')] [string]$Kind = 'Info')
    Write-Output $Text
    if ($NoDialog) { return }
    Add-Type -AssemblyName System.Windows.Forms
    $icon = if ($Kind -eq 'Error') { [System.Windows.Forms.MessageBoxIcon]::Error } else { [System.Windows.Forms.MessageBoxIcon]::Information }
    [void][System.Windows.Forms.MessageBox]::Show($Text, $Title, [System.Windows.Forms.MessageBoxButtons]::OK, $icon)
}

function Get-ExpectedHash {
    if (-not (Test-Path -LiteralPath $ChecksumFile -PathType Leaf)) {
        throw "Missing checksum file: $ChecksumFile"
    }
    $line = (Get-Content -LiteralPath $ChecksumFile -TotalCount 1).Trim()
    $hash = ($line -split '\s+')[0].Trim().ToUpperInvariant()
    if ($hash -notmatch '^[A-F0-9]{64}$') { throw 'Invalid SHA-256 checksum file.' }
    return $hash
}

function Get-Mt5DataFolders {
    $terminalRoot = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    if (-not (Test-Path -LiteralPath $terminalRoot -PathType Container)) { return @() }
    return @(Get-ChildItem -LiteralPath $terminalRoot -Directory -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ne 'Common' -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'origin.txt') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'MQL5') -PathType Container)
    })
}

function Get-InstallRows {
    param([System.IO.DirectoryInfo[]]$DataFolders, [string]$ExpectedHash)
    foreach ($folder in $DataFolders) {
        $origin = (Get-Content -LiteralPath (Join-Path $folder.FullName 'origin.txt') -ErrorAction SilentlyContinue | Select-Object -First 1)
        $target = Join-Path $folder.FullName "MQL5\Experts\$EaName"
        $installedHash = if (Test-Path -LiteralPath $target -PathType Leaf) { (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant() } else { '' }
        [pscustomobject]@{
            DataFolder = $folder.FullName
            Terminal = if ($origin) { $origin.Trim() } else { $folder.Name }
            Target = $target
            Installed = [bool]$installedHash
            Current = $installedHash -eq $ExpectedHash
        }
    }
}

try {
    $expectedHash = Get-ExpectedHash
    $folders = @(Get-Mt5DataFolders)
    if ($folders.Count -eq 0) { throw 'No MT5 Data Folder found. Open MT5 once, then run Setup again.' }
    $rows = @(Get-InstallRows -DataFolders $folders -ExpectedHash $expectedHash)

    if ($Action -eq 'Status') {
        $summary = ($rows | ForEach-Object { "$(if ($_.Current) {'OK'} elseif ($_.Installed) {'OLD'} else {'MISS'}) | $($_.Terminal)" }) -join "`r`n"
        Show-OakMessage -Text "NeoTech C5 status:`r`n`r`n$summary"
        exit 0
    }

    if ($Action -eq 'Uninstall') {
        $removed = 0
        foreach ($row in $rows) {
            if (-not (Test-Path -LiteralPath $row.Target -PathType Leaf)) { continue }
            if (-not $DryRun) { Remove-Item -LiteralPath $row.Target -Force }
            $removed++
        }
        $verb = if ($DryRun) { 'would remove' } else { 'removed' }
        Show-OakMessage -Text "NeoTech C5: $verb from $removed MT5 terminal(s)."
        exit 0
    }

    if (-not (Test-Path -LiteralPath $SourceEx5 -PathType Leaf)) { throw "Missing EA file: $SourceEx5" }
    $sourceHash = (Get-FileHash -LiteralPath $SourceEx5 -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($sourceHash -ne $expectedHash) { throw 'EA SHA-256 mismatch. Setup stopped before copying anything.' }

    $installed = 0
    $already = 0
    foreach ($row in $rows) {
        if ($row.Current) { $already++; continue }
        if (-not $DryRun) {
            $experts = Split-Path -Parent $row.Target
            New-Item -ItemType Directory -Path $experts -Force | Out-Null
            Copy-Item -LiteralPath $SourceEx5 -Destination $row.Target -Force
            Unblock-File -LiteralPath $row.Target -ErrorAction SilentlyContinue
            $writtenHash = (Get-FileHash -LiteralPath $row.Target -Algorithm SHA256).Hash.ToUpperInvariant()
            if ($writtenHash -ne $expectedHash) {
                Remove-Item -LiteralPath $row.Target -Force -ErrorAction SilentlyContinue
                throw "Verification failed after copying to $($row.Terminal)."
            }
        }
        $installed++
    }

    $verb = if ($DryRun) { 'Would install' } else { 'Installed' }
    $next = if ($DryRun) { '' } else { "`r`n`r`nFinal step: in MT5, Refresh Navigator > Expert Advisors and attach OAK_NeoTech_Compliance_EA to one chart. If an older EA is already attached, restart MT5 once.`r`n`r`nLocal C5 popup works immediately. Click C5 LOOK on the chart to see symbols already used in the current session." }
    Show-OakMessage -Text "$verb NeoTech C5 for $installed terminal(s); $already terminal(s) were already current.$next"
    exit 0
}
catch {
    Show-OakMessage -Text ("Setup did not complete: " + $_.Exception.Message) -Kind Error
    exit 1
}
