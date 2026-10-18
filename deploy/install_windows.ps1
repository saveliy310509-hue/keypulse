# install_windows.ps1 - KeyPulse as a Windows background task
#
# What it does:
#   1. creates .venv and installs dependencies
#   2. registers a Scheduled Task: start at logon
#   3. restarts the bot every minute if it crashes (unlimited attempts)
#   4. starts it right away, hidden (no console window)
#
# Run (PowerShell as Administrator):
#   powershell -ExecutionPolicy Bypass -File .\deploy\install_windows.ps1
#
# Remove:
#   Unregister-ScheduledTask -TaskName "KeyPulseBot" -Confirm:$false

param(
    [string]$TaskName = "KeyPulseBot",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location $projectDir

$python = Join-Path $projectDir ".venv\Scripts\python.exe"
$vbs = Join-Path $projectDir "deploy\start_hidden.vbs"
$logDir = Join-Path $projectDir "logs"

if (-not (Test-Path $vbs)) {
    throw "start_hidden.vbs not found in deploy/"
}

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

if (-not $SkipInstall) {
    if (-not (Test-Path $python)) {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
    }
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $python -m pip install --upgrade pip --quiet
    & $python -m pip install -r requirements.txt --quiet
}

$envFile = Join-Path $projectDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "WARNING: .env not found - copy .env.example and set BOT_TOKEN" -ForegroundColor Yellow
}

Write-Host "Registering task $TaskName..." -ForegroundColor Cyan

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"' + $vbs + '"') -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "KeyPulse Telegram bot (HWID license keys)" -Force | Out-Null

Write-Host "Starting task..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5

$state = (Get-ScheduledTask -TaskName $TaskName).State
$proc = Get-Process python -ErrorAction SilentlyContinue

Write-Host ""
Write-Host ("Task state: " + $state) -ForegroundColor Green
if ($proc) {
    Write-Host ("python processes: " + $proc.Count) -ForegroundColor Green
} else {
    Write-Host "No python process - check logs\bot.err.log" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host ("  Get-ScheduledTask -TaskName " + $TaskName + " | Get-ScheduledTaskInfo")
Write-Host "  Get-Content .\logs\bot.log -Tail 30 -Wait"
Write-Host ("  Stop-ScheduledTask -TaskName " + $TaskName)
Write-Host ("  Start-ScheduledTask -TaskName " + $TaskName)
Write-Host ""
Write-Host "The bot starts on logon and self-restarts after crashes." -ForegroundColor Green
Write-Host "Keep the PC awake: powercfg /change standby-timeout-ac 0" -ForegroundColor Yellow
