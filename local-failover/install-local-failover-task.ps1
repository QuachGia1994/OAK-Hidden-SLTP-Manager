param(
  [ValidateSet("Install", "Uninstall", "Status", "Doctor")]
  [string]$Action = "Doctor",
  [switch]$DryRun,
  [string]$ConfigPath = "",
  [string]$CommonDir = ""
)

$ErrorActionPreference = "Stop"
$TaskName = "OAK Local Telegram Failover"
$WatchdogTaskName = "OAK Local Telegram Failover Watchdog"
$Script = Join-Path $PSScriptRoot "oak-local-telegram-failover.mjs"
$WatchdogScript = Join-Path $PSScriptRoot "watch-local-failover.ps1"
$HiddenLauncher = Join-Path $PSScriptRoot "run-hidden-node.vbs"
$Domain = Join-Path $PSScriptRoot "oak-local-failover-domain.mjs"
$RuntimeDir = Join-Path $env:LOCALAPPDATA "OAK Gatekeeper"
if (-not $ConfigPath) { $ConfigPath = Join-Path $RuntimeDir "telegram-failover-config.json" }
if (-not $CommonDir) { $CommonDir = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files\OAKLocalFailover" }

function Get-CurrentIdentityInfo {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not $identity.User) { throw "Current Windows SID is unavailable" }
  [pscustomobject]@{ Name = $identity.Name; Sid = $identity.User.Value }
}

function Get-NodeInfo {
  $node = (Get-Command node.exe -ErrorAction Stop).Source
  $versionText = (& $node --version).Trim()
  if ($LASTEXITCODE -ne 0 -or $versionText -notmatch '^v(\d+)\.') { throw "Unable to determine Node.js version" }
  $major = [int]$Matches[1]
  if ($major -lt 22) { throw "Node.js 22+ is required; found $versionText" }
  [pscustomobject]@{ Path = $node; Version = $versionText; Major = $major }
}

function Test-NodeImportGraph([string]$NodePath) {
  $controllerUri = ([Uri]$Script).AbsoluteUri
  & $NodePath --input-type=module -e "await import(process.argv[1]);" $controllerUri | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Node cannot import the local failover controller dependency graph (including the MT5 UI adapter)" }
}

function Test-ConfigAcl {
  if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "Local failover config not found: $ConfigPath" }
  $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
  $configFull = [IO.Path]::GetFullPath($ConfigPath)
  if ($configFull.StartsWith($repoRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Runtime config must be outside the Git repository" }
  $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
  if (@(2, 3) -notcontains [int]$config.v -or -not $config.telegramToken -or -not $config.telegramChatId -or -not $config.telegramWebhookSecret) {
    throw "Local failover config v2/v3 is incomplete"
  }
  if ([int]$config.v -eq 2 -and (-not $config.upstashUrl -or -not $config.upstashToken)) {
    throw "Local failover config v2 requires Upstash REST credentials"
  }
  if ([int]$config.v -eq 3) {
    if ([string]$config.controlMode -ne "local-primary") { throw "Local failover config v3 requires controlMode=local-primary" }
    $driver = if ($config.scheduledEntryExecution) { [string]$config.scheduledEntryExecution } else { "ea" }
    if (@("ea", "mt5-ui") -notcontains $driver.ToLowerInvariant()) { throw "Local failover config v3 has an unsupported scheduled-entry driver" }
  }
  $acl = Get-Acl -LiteralPath $ConfigPath
  if (-not $acl.AreAccessRulesProtected) { throw "Runtime config ACL still inherits permissions; bootstrap must apply user-only ACL" }
  $identity = Get-CurrentIdentityInfo
  $allowed = @($acl.Access | Where-Object { $_.IdentityReference.Value -eq $identity.Name -and $_.AccessControlType -eq "Allow" })
  if ($allowed.Count -eq 0) { throw "Current Windows user has no explicit ACL entry on runtime config" }
}

function Test-Mt5UserContext {
  $identity = Get-CurrentIdentityInfo
  $processes = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue)
  if ($processes.Count -eq 0) { throw "No terminal64.exe is running for same-user validation" }
  foreach ($process in $processes) {
    $owner = Invoke-CimMethod -InputObject $process -MethodName GetOwner -ErrorAction SilentlyContinue
    if ($owner -and ("{0}\{1}" -f $owner.Domain, $owner.User) -eq $identity.Name) { return }
  }
  throw "MT5 terminal is not running under the current Windows user"
}

function Invoke-Doctor {
  if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { throw "Failover controller not found: $Script" }
  if (-not (Test-Path -LiteralPath $HiddenLauncher -PathType Leaf)) { throw "Hidden launcher not found: $HiddenLauncher" }
  if (-not (Test-Path -LiteralPath $WatchdogScript -PathType Leaf)) { throw "Failover watchdog not found: $WatchdogScript" }
  if (-not (Test-Path -LiteralPath $Domain -PathType Leaf)) { throw "Failover domain not found: $Domain" }
  $node = Get-NodeInfo
  Test-NodeImportGraph $node.Path
  $identity = Get-CurrentIdentityInfo
  Test-ConfigAcl
  if (-not (Test-Path -LiteralPath $CommonDir -PathType Container)) { throw "MT5 FILE_COMMON failover directory not found: $CommonDir" }
  Test-Mt5UserContext
  [pscustomobject]@{
    ok = $true
    dryRunSafeChecksOnly = $true
    nodePath = $node.Path
    nodeVersion = $node.Version
    controller = $Script
    configPath = $ConfigPath
    commonDir = $CommonDir
    windowsUser = $identity.Name
    windowsSid = $identity.Sid
    mutationsPerformed = 0
  }
}

function New-FailoverTaskDefinition {
  $node = Get-NodeInfo
  $identity = Get-CurrentIdentityInfo
  $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
  if (-not (Test-Path -LiteralPath $wscript -PathType Leaf)) { throw "Windows Script Host unavailable: $wscript" }
  $arguments = '"{0}" "{1}" "{2}"' -f $HiddenLauncher, $node.Path, $Script
  $taskAction = New-ScheduledTaskAction -Execute $wscript -Argument $arguments -WorkingDirectory $PSScriptRoot
  $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
  New-ScheduledTask -Action $taskAction -Trigger @($logonTrigger) -Settings $settings -Principal $principal
}

function New-FailoverWatchdogTaskDefinition {
  $identity = Get-CurrentIdentityInfo
  $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
  if (-not (Test-Path -LiteralPath $powershell -PathType Leaf)) { throw "Windows PowerShell unavailable: $powershell" }
  $statePath = Join-Path $RuntimeDir "state.json"
  $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -TaskName "{1}" -StatePath "{2}" -MaxStaleSeconds 120' -f $WatchdogScript, $TaskName, $statePath
  $taskAction = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $PSScriptRoot
  $watchdogStart = (Get-Date).AddMinutes(1)
  $watchdogTrigger = New-ScheduledTaskTrigger -Once -At $watchdogStart -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
  New-ScheduledTask -Action $taskAction -Trigger @($watchdogTrigger) -Settings $settings -Principal $principal
}

try {
  switch ($Action) {
    "Doctor" {
      $report = Invoke-Doctor
      $report | ConvertTo-Json -Depth 4
      exit 0
    }
    "Status" {
      $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
      $watchdogTask = Get-ScheduledTask -TaskName $WatchdogTaskName -ErrorAction SilentlyContinue
      [pscustomobject]@{
        installed = [bool]$task
        state = if ($task) { [string]$task.State } else { "Absent" }
        watchdogInstalled = [bool]$watchdogTask
        watchdogState = if ($watchdogTask) { [string]$watchdogTask.State } else { "Absent" }
        mutationsPerformed = 0
      } | ConvertTo-Json
      exit 0
    }
    "Install" {
      $null = Invoke-Doctor
      $definition = New-FailoverTaskDefinition
      $watchdogDefinition = New-FailoverWatchdogTaskDefinition
      if ($DryRun) {
        [pscustomobject]@{ ok = $true; dryRun = $true; action = "Install"; taskName = $TaskName; watchdogTaskName = $WatchdogTaskName; multipleInstances = "IgnoreNew"; restartCount = 999; watchdogEveryMinutes = 1; watchdogStaleSeconds = 120; allowStartOnBatteries = $true; stopIfGoingOnBatteries = $false; logonType = "Interactive"; windowMode = "hidden-wscript"; mutationsPerformed = 0 } | ConvertTo-Json
        exit 0
      }
      Register-ScheduledTask -TaskName $TaskName -InputObject $definition -Force | Out-Null
      Register-ScheduledTask -TaskName $WatchdogTaskName -InputObject $watchdogDefinition -Force | Out-Null
      Write-Output "Installed: $TaskName + watchdog (starts at logon; no password stored)"
      exit 0
    }
    "Uninstall" {
      $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
      $watchdogTask = Get-ScheduledTask -TaskName $WatchdogTaskName -ErrorAction SilentlyContinue
      if ($DryRun) {
        [pscustomobject]@{ ok = $true; dryRun = $true; action = "Uninstall"; installed = [bool]$task; watchdogInstalled = [bool]$watchdogTask; mutationsPerformed = 0 } | ConvertTo-Json
        exit 0
      }
      if ($watchdogTask) {
        Stop-ScheduledTask -TaskName $WatchdogTaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $WatchdogTaskName -Confirm:$false
      }
      if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
      }
      Write-Output "Uninstalled: $TaskName + watchdog"
      exit 0
    }
  }
} catch {
  Write-Error $_.Exception.Message
  exit 2
}
