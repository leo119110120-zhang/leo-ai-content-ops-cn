param(
    [string]$Root = (Resolve-Path "$PSScriptRoot\.."),
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$name = "LeoContentOpsDaily"
$resolvedRoot = (Resolve-Path $Root).Path
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$arguments = "-m content_ops.cli daily --root `"$resolvedRoot`""
$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument $arguments `
    -WorkingDirectory $resolvedRoot
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At '10:30'
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $name `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Leo AI content candidate scan" `
    -Force | Out-Null

Write-Output "Installed $name at 10:30 Monday-Friday for $resolvedRoot"
