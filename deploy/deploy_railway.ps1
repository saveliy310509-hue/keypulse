# deploy_railway.ps1 - deploy KeyPulse to Railway in one command
#
# Requires:
#   1) Node.js (for CLI) and a Railway account
#   2) Token: Railway -> Account Settings -> Tokens -> Create Token
#
# Usage:
#   $env:RAILWAY_TOKEN = "your_token"
#   powershell -ExecutionPolicy Bypass -File .\deploy\deploy_railway.ps1

param(
    [string]$Token = $env:RAILWAY_TOKEN,
    [string]$ProjectName = "keypulse"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ([string]::IsNullOrWhiteSpace($Token)) {
    Write-Host "RAILWAY_TOKEN is empty. Get one: Railway -> Account Settings -> Tokens" -ForegroundColor Yellow
    exit 1
}
$env:RAILWAY_TOKEN = $Token

$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) {
    Write-Host ".env not found" -ForegroundColor Red
    exit 1
}

$vars = @{}
foreach ($line in Get-Content $envPath) {
    if ($line -match "^\s*#") { continue }
    if ($line -notmatch "=") { continue }
    $k, $v = $line -split "=", 2
    $vars[$k.Trim()] = $v.Trim()
}

if (-not $vars["BOT_TOKEN"]) {
    Write-Host "BOT_TOKEN missing in .env" -ForegroundColor Red
    exit 1
}
if (-not $vars["ADMIN_ID"]) {
    Write-Host "ADMIN_ID missing in .env" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Railway CLI..." -ForegroundColor Cyan
    npm install -g @railway/cli
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CLI install failed. Install Node.js and retry." -ForegroundColor Red
        exit 1
    }
}

Write-Host "=== Init project ===" -ForegroundColor Cyan
railway init --name $ProjectName

$apiSecret = $vars["API_SECRET"]
if ([string]::IsNullOrWhiteSpace($apiSecret)) {
    $alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    $chars = @()
    for ($i = 0; $i -lt 40; $i++) {
        $chars += $alphabet[(Get-Random -Maximum $alphabet.Length)]
    }
    $apiSecret = -join $chars
}

Write-Host "=== Environment variables ===" -ForegroundColor Cyan
railway variables --set "BOT_TOKEN=$($vars['BOT_TOKEN'])" --set "ADMIN_ID=$($vars['ADMIN_ID'])" --set "API_SECRET=$apiSecret" --set "DATABASE_PATH=/app/data/keypulse.db"

Write-Host "=== Volume for SQLite ===" -ForegroundColor Cyan
try {
    railway volume add --mount-path /app/data
} catch {
    Write-Host "Add volume manually: Settings -> Volumes -> /app/data" -ForegroundColor Yellow
}

Write-Host "=== Deploy ===" -ForegroundColor Cyan
railway up --detach

Write-Host "=== Domain ===" -ForegroundColor Cyan
try {
    railway domain
} catch {
    Write-Host "Generate domain: Settings -> Networking -> Generate Domain" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Check:" -ForegroundColor Green
Write-Host "  railway logs"
Write-Host "  https://your-domain/health"
Write-Host "  /start in Telegram"
