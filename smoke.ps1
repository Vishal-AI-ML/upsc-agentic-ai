# UPSC AI Pro - local smoke test (PowerShell)
# Usage:  powershell -ExecutionPolicy Bypass -File .\smoke.ps1
# Pehle server chalao (dusre terminal mein):  uv run uvicorn src.api.main:app --reload
# Aur demo user banao (ek baar):               uv run python scripts/make_demo_user.py

$ErrorActionPreference = "Stop"

# Console ko UTF-8 pe set karo taaki Hindi (Devanagari) sahi dikhe (gibberish na ho).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$base  = "http://127.0.0.1:8000/api/v1"
$email = "demo@upsc.local"
$pass  = "Demo@12345"

Write-Host "1) Login..." -ForegroundColor Cyan
$login = Invoke-RestMethod -Uri "$base/auth/login" -Method Post -Body @{ username = $email; password = $pass }
$token = $login.access_token
Write-Host "   token mila ($($token.Length) chars)" -ForegroundColor Green

$headers = @{ Authorization = "Bearer $token" }

Write-Host "`n2) /mentor/chat/sync ..." -ForegroundColor Cyan
$sync = Invoke-RestMethod -Uri "$base/mentor/chat/sync" -Method Post -ContentType "application/json" -Headers $headers -Body '{"question":"UPSC Prelims 2026 kab hai?"}'
$sync | ConvertTo-Json -Depth 5

Write-Host "`n3) /mentor/chat (streaming, token-by-token) ..." -ForegroundColor Cyan
# PowerShell curl.exe ko inline JSON dene par double-quotes kha jaata hai;
# isliye body ko temp file mein likh ke --data "@file" se bhejte hain (reliable).
$body3 = '{"question":"Bhai 2 line mein motivate karo"}'
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $body3, (New-Object System.Text.UTF8Encoding($false)))
try {
    curl.exe -N -X POST "$base/mentor/chat" -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data "@$tmp"
} finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
Write-Host ""
Write-Host "`nDone." -ForegroundColor Green
