param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("prepare", "submit", "close")]
  [string]$Mode,
  [Parameter(Mandatory = $true)]
  [string]$TaskPath,
  [Parameter(Mandatory = $true)]
  [string]$PreparedPath,
  [Parameter(Mandatory = $true)]
  [string]$ResultPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class OakMt5UiWin32 {
  [DllImport("user32.dll", CharSet=CharSet.Unicode)]
  public static extern IntPtr SendMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);

  [DllImport("user32.dll", CharSet=CharSet.Unicode)]
  public static extern IntPtr SendMessage(IntPtr hWnd, uint message, IntPtr wParam, string lParam);

  [DllImport("user32.dll", CharSet=CharSet.Unicode)]
  public static extern IntPtr SendMessage(IntPtr hWnd, uint message, IntPtr wParam, StringBuilder lParam);

  [DllImport("user32.dll")]
  public static extern bool PostMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool IsWindowEnabled(IntPtr hWnd);

  [DllImport("user32.dll", CharSet=CharSet.Unicode)]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

$WM_CLOSE = 0x0010
$WM_SETTEXT = 0x000C
$WM_GETTEXT = 0x000D
$WM_COMMAND = 0x0111
$WM_KEYDOWN = 0x0100
$WM_KEYUP = 0x0101
$BM_CLICK = 0x00F5
$VK_RETURN = 0x0D
$CBN_EDITCHANGE = 5
$NEW_ORDER_COMMAND = 32848

function Get-UtcMs {
  return [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
}

function Write-Result([hashtable]$value) {
  $parent = Split-Path -Parent $ResultPath
  if ($parent) {
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
  }
  $json = $value | ConvertTo-Json -Depth 8 -Compress
  [System.IO.File]::WriteAllText($ResultPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Read-Json([string]$file) {
  if (-not [System.IO.File]::Exists($file)) {
    throw "Required MT5 UI state file is missing"
  }
  return Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-WindowTitle([IntPtr]$handle) {
  $buffer = [System.Text.StringBuilder]::new(1024)
  [void][OakMt5UiWin32]::GetWindowText($handle, $buffer, $buffer.Capacity)
  return $buffer.ToString()
}

function Read-ControlText([IntPtr]$handle) {
  if ($handle -eq [IntPtr]::Zero) {
    throw "MT5 UI control handle is unavailable"
  }
  $buffer = [System.Text.StringBuilder]::new(512)
  [void][OakMt5UiWin32]::SendMessage($handle, $WM_GETTEXT, [IntPtr]$buffer.Capacity, $buffer)
  return $buffer.ToString()
}

function Set-ControlText([IntPtr]$handle, [string]$value) {
  if ($handle -eq [IntPtr]::Zero) {
    throw "MT5 UI control handle is unavailable"
  }
  [void][OakMt5UiWin32]::SendMessage($handle, $WM_SETTEXT, [IntPtr]::Zero, $value)
}

function Get-TerminalProcess($task) {
  $login = [string][long]$task.login
  $server = [string]$task.server
  if (-not $login -or -not $server) {
    throw "MT5 UI task has incomplete terminal identity"
  }

  $pattern = "^" + [regex]::Escape($login) + "\s+-\s+" + [regex]::Escape($server) + "(?:\s+-|\s*:)"
  $matches = @(
    Get-Process -Name "terminal64" -ErrorAction SilentlyContinue |
      Where-Object { [string]$_.MainWindowTitle -match $pattern }
  )

  if ($matches.Count -ne 1) {
    throw "Expected exactly one terminal64 window for login/server; found $($matches.Count)"
  }

  $process = $matches[0]
  if ($process.MainWindowHandle -eq [IntPtr]::Zero) {
    throw "Matched MT5 terminal has no main window"
  }

  $expectedPath = [string]$task.terminalPath
  if ($expectedPath) {
    $actualPath = [System.IO.Path]::GetFullPath([string]$process.Path)
    $normalizedExpected = [System.IO.Path]::GetFullPath($expectedPath)
    if (-not $actualPath.Equals($normalizedExpected, [StringComparison]::OrdinalIgnoreCase)) {
      throw "Matched MT5 terminal executable path differs from configured terminalPath"
    }
  }

  return $process
}

function Get-MainElement([IntPtr]$mainHandle) {
  $element = [System.Windows.Automation.AutomationElement]::FromHandle($mainHandle)
  if ($null -eq $element) {
    throw "MT5 main window is unavailable to UI Automation"
  }
  return $element
}

function Find-OrderDialog([System.Windows.Automation.AutomationElement]$mainElement) {
  $nodes = $mainElement.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
  )
  foreach ($node in $nodes) {
    if ($node.Current.ClassName -eq "#32770" -and [string]$node.Current.Name -like "Order:*") {
      return $node
    }
  }
  return $null
}

function Wait-OrderDialog([System.Windows.Automation.AutomationElement]$mainElement, [int]$timeoutMs = 3000) {
  $deadline = (Get-UtcMs) + $timeoutMs
  do {
    $dialog = Find-OrderDialog $mainElement
    if ($null -ne $dialog) {
      return $dialog
    }
    Start-Sleep -Milliseconds 50
  } while ((Get-UtcMs) -lt $deadline)
  throw "MT5 order dialog did not open before timeout"
}

function Get-ControlElement(
  [System.Windows.Automation.AutomationElement]$dialog,
  [string]$automationId
) {
  $condition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
    $automationId
  )
  $element = $dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
  if ($null -eq $element) {
    throw "Required MT5 order control $automationId was not found"
  }
  if (-not $element.Current.IsEnabled) {
    throw "Required MT5 order control $automationId is disabled"
  }
  return $element
}

function Get-ControlHandle(
  [System.Windows.Automation.AutomationElement]$dialog,
  [string]$automationId
) {
  $element = Get-ControlElement $dialog $automationId
  $handle = [IntPtr]$element.Current.NativeWindowHandle
  if ($handle -eq [IntPtr]::Zero) {
    throw "Required MT5 order control $automationId has no native handle"
  }
  return $handle
}

function Assert-DialogProcess([IntPtr]$dialogHandle, [int]$expectedProcessId) {
  [uint32]$actualProcessId = 0
  [void][OakMt5UiWin32]::GetWindowThreadProcessId($dialogHandle, [ref]$actualProcessId)
  if ([int]$actualProcessId -ne $expectedProcessId) {
    throw "MT5 order dialog process identity changed"
  }
}

function Parse-InvariantNumber([string]$text, [string]$field) {
  [double]$value = 0
  $styles = [System.Globalization.NumberStyles]::Float
  $culture = [System.Globalization.CultureInfo]::InvariantCulture
  if (-not [double]::TryParse($text, $styles, $culture, [ref]$value) -or $value -le 0) {
    throw "MT5 $field field is not a positive invariant number"
  }
  return $value
}

function Assert-NumericField([IntPtr]$handle, [string]$expectedText, [string]$field) {
  $actualText = Read-ControlText $handle
  $actual = Parse-InvariantNumber $actualText $field
  $expected = Parse-InvariantNumber $expectedText $field
  $tolerance = [Math]::Max(0.00000001, [Math]::Abs($expected) * 0.000000001)
  if ([Math]::Abs($actual - $expected) -gt $tolerance) {
    throw "MT5 $field read-back differs from the prepared value"
  }
}

function Assert-PreparedFields(
  [System.Windows.Automation.AutomationElement]$dialog,
  $task
) {
  $dialogHandle = [IntPtr]$dialog.Current.NativeWindowHandle
  $dialogTitle = Get-WindowTitle $dialogHandle
  if ($dialogTitle -notlike "Order: $([string]$task.symbol)*") {
    throw "MT5 order dialog symbol/title changed before submit"
  }

  $symbolHandle = Get-ControlHandle $dialog "10325"
  $symbolText = Read-ControlText $symbolHandle
  if ($symbolText -notlike "$([string]$task.symbol)*") {
    throw "MT5 symbol read-back differs from the prepared symbol"
  }

  Assert-NumericField (Get-ControlHandle $dialog "10333") ([string]$task.volumeText) "volume"
  Assert-NumericField (Get-ControlHandle $dialog "10334") ([string]$task.slText) "stop loss"
  Assert-NumericField (Get-ControlHandle $dialog "10336") ([string]$task.tpText) "take profit"

  $comment = Read-ControlText (Get-ControlHandle $dialog "1001")
  if ($comment -ne [string]$task.comment) {
    throw "MT5 comment read-back differs from the idempotency comment"
  }
}

function Close-OrderDialog([System.Windows.Automation.AutomationElement]$dialog) {
  if ($null -eq $dialog) {
    return $false
  }
  $handle = [IntPtr]$dialog.Current.NativeWindowHandle
  if ($handle -eq [IntPtr]::Zero) {
    return $false
  }
  return [OakMt5UiWin32]::PostMessage($handle, $WM_CLOSE, [IntPtr]::Zero, [IntPtr]::Zero)
}

$task = Read-Json $TaskPath
$openedByThisRun = $false
$openedDialog = $null

try {
  $process = Get-TerminalProcess $task
  $mainHandle = [IntPtr]$process.MainWindowHandle
  $mainElement = Get-MainElement $mainHandle

  if ($Mode -eq "close") {
    $dialog = Find-OrderDialog $mainElement
    $closed = Close-OrderDialog $dialog
    Write-Result @{
      ok = $true
      closed = [bool]$closed
      at = Get-UtcMs
    }
    exit 0
  }

  if ($Mode -eq "prepare") {
    $existingDialog = Find-OrderDialog $mainElement
    if ($null -ne $existingDialog) {
      throw "An MT5 order dialog is already open; scheduled entry stopped without touching it"
    }

    $opened = [OakMt5UiWin32]::PostMessage(
      $mainHandle,
      $WM_COMMAND,
      [IntPtr]$NEW_ORDER_COMMAND,
      [IntPtr]::Zero
    )
    if (-not $opened) {
      throw "MT5 rejected the internal New Order command (possible Windows integrity mismatch; run the controller and terminal at the same elevation)"
    }

    $openedDialog = Wait-OrderDialog $mainElement
    $openedByThisRun = $true
    $dialogHandle = [IntPtr]$openedDialog.Current.NativeWindowHandle
    Assert-DialogProcess $dialogHandle $process.Id

    $symbolCombo = Get-ControlHandle $openedDialog "10331"
    $symbolEdit = Get-ControlHandle $openedDialog "10325"
    Set-ControlText $symbolEdit ([string]$task.symbol)

    $editChange = [IntPtr](10331 -bor ($CBN_EDITCHANGE -shl 16))
    [void][OakMt5UiWin32]::SendMessage($dialogHandle, $WM_COMMAND, $editChange, $symbolCombo)
    [void][OakMt5UiWin32]::PostMessage($symbolEdit, $WM_KEYDOWN, [IntPtr]$VK_RETURN, [IntPtr]1)
    [void][OakMt5UiWin32]::PostMessage($symbolEdit, $WM_KEYUP, [IntPtr]$VK_RETURN, [IntPtr]0xC0000001)

    $symbolDeadline = (Get-UtcMs) + 2500
    do {
      Start-Sleep -Milliseconds 50
      $dialogTitle = Get-WindowTitle $dialogHandle
      $symbolText = Read-ControlText $symbolEdit
      if ($dialogTitle -like "Order: $([string]$task.symbol)*" -and $symbolText -like "$([string]$task.symbol)*") {
        break
      }
    } while ((Get-UtcMs) -lt $symbolDeadline)

    if ($dialogTitle -notlike "Order: $([string]$task.symbol)*" -or $symbolText -notlike "$([string]$task.symbol)*") {
      throw "MT5 did not accept the prepared symbol"
    }

    Set-ControlText (Get-ControlHandle $openedDialog "10333") ([string]$task.volumeText)
    Set-ControlText (Get-ControlHandle $openedDialog "10334") ([string]$task.slText)
    Set-ControlText (Get-ControlHandle $openedDialog "10336") ([string]$task.tpText)
    Set-ControlText (Get-ControlHandle $openedDialog "1001") ([string]$task.comment)
    Start-Sleep -Milliseconds 75

    Assert-PreparedFields $openedDialog $task

    $buttonId = if ([string]$task.side -eq "BUY") { "10408" } elseif ([string]$task.side -eq "SELL") { "10409" } else { throw "MT5 UI side must be BUY or SELL" }
    $buttonHandle = Get-ControlHandle $openedDialog $buttonId
    if (-not [OakMt5UiWin32]::IsWindowEnabled($buttonHandle)) {
      throw "Prepared MT5 Buy/Sell button is disabled"
    }

    Write-Result @{
      ok = $true
      pid = $process.Id
      mainWindowHandle = $mainHandle.ToInt64()
      dialogHandle = $dialogHandle.ToInt64()
      side = [string]$task.side
      symbol = [string]$task.symbol
      volumeText = [string]$task.volumeText
      slText = [string]$task.slText
      tpText = [string]$task.tpText
      comment = [string]$task.comment
      preparedAt = Get-UtcMs
    }
    exit 0
  }

  $prepared = Read-Json $PreparedPath
  if ($prepared.ok -ne $true) {
    throw "MT5 UI prepared state is not successful"
  }
  if ([int]$prepared.pid -ne $process.Id) {
    throw "MT5 terminal process changed after order preparation"
  }

  $dialog = Find-OrderDialog $mainElement
  if ($null -eq $dialog) {
    throw "Prepared MT5 order dialog disappeared before submit"
  }
  $dialogHandle = [IntPtr]$dialog.Current.NativeWindowHandle
  if ($dialogHandle.ToInt64() -ne [long]$prepared.dialogHandle) {
    throw "MT5 order dialog handle changed before submit"
  }

  Assert-DialogProcess $dialogHandle $process.Id
  Assert-PreparedFields $dialog $task

  $submitButtonId = if ([string]$task.side -eq "BUY") { "10408" } elseif ([string]$task.side -eq "SELL") { "10409" } else { throw "MT5 UI side must be BUY or SELL" }
  $submitButton = Get-ControlHandle $dialog $submitButtonId
  if (-not [OakMt5UiWin32]::IsWindowEnabled($submitButton)) {
    throw "MT5 Buy/Sell button became disabled before submit"
  }

  $queued = [OakMt5UiWin32]::PostMessage($submitButton, $BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
  if (-not $queued) {
    throw "MT5 Buy/Sell button message was not queued"
  }

  Write-Result @{
    ok = $true
    submitted = $true
    pid = $process.Id
    dialogHandle = $dialogHandle.ToInt64()
    submittedAt = Get-UtcMs
  }
  exit 0
} catch {
  if ($Mode -eq "prepare" -and $openedByThisRun -and $null -ne $openedDialog) {
    [void](Close-OrderDialog $openedDialog)
  }
  Write-Result @{
    ok = $false
    submitted = $false
    error = [string]$_.Exception.Message
    at = Get-UtcMs
  }
  exit 0
}
