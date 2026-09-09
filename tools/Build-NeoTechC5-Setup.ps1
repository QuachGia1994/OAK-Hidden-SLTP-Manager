[CmdletBinding()]
param(
    [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Output) { $Output = Join-Path $repo 'dashboard\public\downloads\OAK-NeoTech-C5-Setup.exe' }
$downloads = Join-Path $repo 'dashboard\public\downloads'
$ex5 = Join-Path $downloads 'OAK_NeoTech_Compliance_EA.ex5'
$sha = Join-Path $downloads 'OAK_NeoTech_Compliance_EA.sha256.txt'
$source = Join-Path $PSScriptRoot 'NeoTechC5Setup.cs'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'

foreach ($file in @($ex5,$sha,$source,$csc)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing build input: $file" }
}

$expected = ((Get-Content -LiteralPath $sha -TotalCount 1).Trim() -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $ex5 -Algorithm SHA256).Hash
if ($expected -ne $actual) { throw 'Public EX5 does not match its SHA-256 file.' }

$targetDir = Split-Path -Parent $Output
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Force }

$args = @(
    '/nologo',
    '/target:winexe',
    '/platform:anycpu',
    '/optimize+',
    '/warn:4',
    '/warnaserror+',
    '/reference:System.Windows.Forms.dll',
    "/resource:$ex5,OAK_NeoTech_Compliance_EA.ex5",
    "/resource:$sha,OAK_NeoTech_Compliance_EA.sha256.txt",
    "/out:$Output",
    $source
)

& $csc @args
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Output -PathType Leaf)) {
    throw "C# Setup build failed with exit $LASTEXITCODE"
}

$info = Get-Item -LiteralPath $Output
$hash = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "Built $($info.FullName)"
Write-Output "Size=$($info.Length)"
Write-Output "SHA256=$hash"
