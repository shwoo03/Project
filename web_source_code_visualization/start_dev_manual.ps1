# Web Source Code Visualization - Development Server Starter
# 백엔드/프론트엔드를 백그라운드로 실행하고 로그만 모니터링

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Web Source Code Visualization - Dev Server" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop existing servers
Write-Host "[CLEAN] Stopping existing servers..." -ForegroundColor Yellow

$stopped = $false

# Kill backend (port 8000)
$backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($backend) {
    $backend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Backend (port 8000) stopped" -ForegroundColor Green
    $stopped = $true
}

# Kill frontend (port 3000)
$frontend = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($frontend) {
    $frontend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Frontend (port 3000) stopped" -ForegroundColor Green
    $stopped = $true
}

# Kill any remaining node/python processes related to the project
Get-Process | Where-Object { 
    $_.ProcessName -like "*node*" -or 
    ($_.ProcessName -like "*python*" -and $_.Path -like "*web_source_code_visualization*")
} | Stop-Process -Force -ErrorAction SilentlyContinue

if ($stopped) {
    Write-Host "[OK] Cleanup complete" -ForegroundColor Green
    Start-Sleep -Seconds 1
} else {
    Write-Host "  No servers were running" -ForegroundColor Gray
}

Write-Host ""

# Step 2: Start frontend in background first
Write-Host "[Frontend] Starting on port 3000..." -ForegroundColor Cyan

$frontendPath = Join-Path $PSScriptRoot "frontend"
$frontendProcess = Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "cd '$frontendPath'; npm run dev" -WindowStyle Hidden -PassThru

Write-Host "  Frontend running (PID: $($frontendProcess.Id))" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2

# Step 3: Start backend in current terminal (foreground with full logs)
Write-Host "========================================================" -ForegroundColor Green
Write-Host "[Backend] Starting on port 8000..." -ForegroundColor Cyan
Write-Host ""
Write-Host "   Backend API:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Frontend:     http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "   Backend logs will appear below (AI analysis included)" -ForegroundColor Yellow
Write-Host "   Press Ctrl+C twice to stop (frontend will auto-close)" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

$backendPath = Join-Path $PSScriptRoot "backend"
Set-Location $backendPath

try {
    & ".\venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
}
finally {
    Write-Host ""
    Write-Host "[SHUTDOWN] Stopping frontend..." -ForegroundColor Yellow
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] All servers stopped" -ForegroundColor Green
}

