param(
    [string]$TaskName = "SectorRotationDaily",
    [string]$RunTime = "18:30",
    [string]$ProjectRoot = "D:\Coding\sector-rotation-monitor"
)

$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\run_daily_job.py"

if (-not (Test-Path $PythonPath)) {
    throw "Python not found: $PythonPath"
}
if (-not (Test-Path $ScriptPath)) {
    throw "Script not found: $ScriptPath"
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily A-share sector rotation monitor" `
    -Force

Write-Host "Installed scheduled task '$TaskName' at $RunTime"
