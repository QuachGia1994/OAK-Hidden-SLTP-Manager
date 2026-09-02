param(
  [ValidateSet("Install", "Uninstall", "Status", "Doctor")]
  [string]$Action = "Doctor",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$TaskName = "OAK Local H1 Scanner"
$Script = Join-Path $PSScriptRoot "oak-local-h1-scanner.mjs"
$HiddenLauncher = Join-Path $PSScriptRoot "run-hidden-node.vbs"
$Reader = Join-Path $PSScriptRoot "mt5-h1-market-reader.py"
$ConfigPath = Join-Path $env:LOCALAPPDATA "OAK Gatekeeper\telegram-failover-config.json"

function Get-Identity {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not $identity.User) { throw "Current Windows SID unavailable" }
  [pscustomobject]@{ Name = $identity.Name; Sid = $identity.User.Value }
}

function Get-NodePath {
  $node = (Get-Command node.exe -ErrorAction Stop).Source
  $version = (& $node --version).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Node.js unavailable" }
  return $node
}

function Get-PythonPath {
  $python = (Get-Command python.exe -ErrorAction Stop).Source
  & $python -c "import MetaTrader5" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Python MetaTrader5 package unavailable" }
  return $python
}

function Invoke-Doctor {
  if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { throw "Local H1 scanner not found: $Script" }
  if (-not (Test-Path -LiteralPath $HiddenLauncher -PathType Leaf)) { throw "Hidden launcher not found: $HiddenLauncher" }
  if (-not (Test-Path -LiteralPath $Reader -PathType Leaf)) { throw "MT5 H1 reader not found: $Reader" }
  if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "Local controller config not found: $ConfigPath" }
  $node = Get-NodePath
  $python = Get-PythonPath
  $result = & $node $Script --dry-run | ConvertFrom-Json
  if (-not $result.ok -or -not $result.dryRun) { throw "ICMarkets local H1 dry-run failed" }
  [pscustomobject]@{
    ok = $true
    nodePath = $node
    pythonPath = $python
    brokerDate = $result.brokerDate
    brokerHour = $result.brokerHour
    brokerMinute = $result.brokerMinute
    mutationsPerformed = 0
  }
}

function New-TaskDefinition {
  $node = Get-NodePath
  $identity = Get-Identity
  $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
  if (-not (Test-Path -LiteralPath $wscript -PathType Leaf)) { throw "Windows Script Host unavailable: $wscript" }
  $arguments = '"{0}" "{1}" "{2}"' -f $HiddenLauncher, $node, $Script
  $taskAction = New-ScheduledTaskAction -Execute $wscript -Argument $arguments -WorkingDirectory $PSScriptRoot
  $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
  $start = (Get-Date).AddMinutes(1)
  $repeatTrigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
  New-ScheduledTask -Action $taskAction -Trigger @($logonTrigger, $repeatTrigger) -Settings $settings -Principal $principal
}

try {
  switch ($Action) {
    "Doctor" {
      Invoke-Doctor | ConvertTo-Json -Depth 4
      exit 0
    }
    "Status" {
      $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
      [pscustomobject]@{ installed = [bool]$task; state = if ($task) { [string]$task.State } else { "Absent" }; mutationsPerformed = 0 } | ConvertTo-Json
      exit 0
    }
    "Install" {
      $doctor = Invoke-Doctor
      $definition = New-TaskDefinition
      if ($DryRun) {
        [pscustomobject]@{ ok = $true; dryRun = $true; taskName = $TaskName; everyMinutes = 1; multipleInstances = "IgnoreNew"; brokerDate = $doctor.brokerDate; windowMode = "hidden-wscript"; mutationsPerformed = 0 } | ConvertTo-Json
        exit 0
      }
      Register-ScheduledTask -TaskName $TaskName -InputObject $definition -Force | Out-Null
      Start-ScheduledTask -TaskName $TaskName
      Write-Output "Installed: $TaskName"
      exit 0
    }
    "Uninstall" {
      $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
      if ($DryRun) {
        [pscustomobject]@{ ok = $true; dryRun = $true; installed = [bool]$task; mutationsPerformed = 0 } | ConvertTo-Json
        exit 0
      }
      if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
      }
      Write-Output "Uninstalled: $TaskName"
      exit 0
    }
  }
} catch {
  Write-Error $_.Exception.Message
  exit 2
}
