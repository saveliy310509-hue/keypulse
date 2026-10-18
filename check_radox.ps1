# check_radox.ps1 — быстрая диагностика лимитов Radox AI
# Использование:
#   $env:RADOX_API_KEY = "cc_..."
#   pwsh -File .\check_radox.ps1
#   pwsh -File .\check_radox.ps1 -Model claude-opus-5.5

param(
    [string]$Model = "deepseek-v4-flash-0731",
    [string]$BaseUrl = "https://radoxai.com/v1"
)

function Show-RateHeaders($h) {
    if (-not $h) { return }
    $found = $false
    foreach ($k in $h.Keys) {
        if ($k -match "ratelimit|retry|quota|limit") {
            $found = $true
            Write-Host ("  {0}: {1}" -f $k, ($h[$k] -join ", "))
        }
    }
    if (-not $found) { Write-Host "  (заголовков x-ratelimit-* в ответе нет)" }
}

$key = $env:RADOX_API_KEY
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Host "RADOX_API_KEY не задан. Выполни: `$env:RADOX_API_KEY = 'cc_...'" -ForegroundColor Yellow
    exit 1
}

$headers = @{ Authorization = "Bearer $key"; "Content-Type" = "application/json" }

Write-Host "=== 1. GET /models ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$BaseUrl/models" -Headers $headers -TimeoutSec 30 -UseBasicParsing
    Write-Host "HTTP $($r.StatusCode)"
    $json = $r.Content | ConvertFrom-Json
    Write-Host ("Моделей доступно: " + $json.data.Count)
    Show-RateHeaders $r.Headers
} catch {
    Write-Host "ОШИБКА: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
}

Write-Host "`n=== 2. Минимальный chat/completions (5 токенов) ===" -ForegroundColor Cyan
$body = @{
    model      = $Model
    messages   = @(@{ role = "user"; content = "hi" })
    max_tokens = 5
    stream     = $false
} | ConvertTo-Json -Depth 6

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $r2 = Invoke-WebRequest -Uri "$BaseUrl/chat/completions" -Method Post -Headers $headers -Body $body -TimeoutSec 90 -UseBasicParsing
    $sw.Stop()
    Write-Host "HTTP $($r2.StatusCode) за $($sw.ElapsedMilliseconds) ms" -ForegroundColor Green
    $resp = $r2.Content | ConvertFrom-Json
    Write-Host ("usage: prompt=" + $resp.usage.prompt_tokens + " completion=" + $resp.usage.completion_tokens + " total=" + $resp.usage.total_tokens)
    Show-RateHeaders $r2.Headers
} catch {
    $sw.Stop()
    $resp = $_.Exception.Response
    $code = if ($resp) { [int]$resp.StatusCode } else { "n/a" }
    Write-Host "HTTP $code за $($sw.ElapsedMilliseconds) ms" -ForegroundColor Red
    if ($resp) {
        Show-RateHeaders $resp.Headers
        # PS 7 имеет .Content, PS 5.1 — GetResponseStream()
        if ($resp.PSObject.Properties.Name -contains "Content" -and $resp.Content) {
            $stream = $resp.Content.ReadAsStream()
        } else {
            $stream = $resp.GetResponseStream()
        }
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Host "Тело ответа:" -ForegroundColor Yellow
        Write-Host $reader.ReadToEnd()
    } else {
        Write-Host $_.Exception.Message
    }
}
