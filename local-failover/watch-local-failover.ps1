param(
  [string]$TaskName = "OAK Local Telegram Failover",
  [string]$StatePath = "",
  [int]$MaxStaleSeconds = 120
)

$ErrorActionPreference = "Stop"
if (-not $StatePath) {
  $StatePath = Join-Path $env:LOCALAPPDATA "OAK Gatekeeper\state.json"
}
$MaxStaleSeconds = [Math]::Max(60, [Math]::Min(900, $MaxStaleSeconds))

function Start-MainTaskIfIdle {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $task) { return }
  if ([string]$task.State -ne "Running") {
    Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  }
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
  Start-MainTaskIfIdle
  exit 0
}

try {
  $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
} catch {
  Start-MainTaskIfIdle
  exit 0
}

$lastLoopAt = [int64]($state.lastLoopAt)
$pidValue = [int]($state.lockOwner.pid)
$nowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$staleMs = [int64]$MaxStaleSeconds * 1000
if ($lastLoopAt -le 0 -or ($nowMs - $lastLoopAt) -le $staleMs) {
  Start-MainTaskIfIdle
  exit 0
}

if ($pidValue -gt 0) {
  $process = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
  $commandLine = if ($process) { [string]$process.CommandLine } else { "" }
  $name = if ($process) { [string]$process.Name } else { "" }
  if ($process -and $name -ieq "node.exe" -and $commandLine -match "oak-local-telegram-failover\.mjs") {
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
  }
}

Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
