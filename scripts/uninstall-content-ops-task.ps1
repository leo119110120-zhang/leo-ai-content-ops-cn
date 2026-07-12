$ErrorActionPreference = "Stop"
$name = "LeoContentOpsDaily"

if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
}

Write-Output "Removed $name"
