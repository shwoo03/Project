$ErrorActionPreference = "Stop"

Write-Host "🚀 웹 소스 코드 시각화 프로젝트를 시작합니다..." -ForegroundColor Cyan

$root = Get-Location

# 1. Backend 시작
Write-Host "Starting Backend Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; if (Test-Path 'venv') { .\venv\Scripts\activate } else { python -m venv venv; .\venv\Scripts\activate; pip install -r requirements.txt }; uvicorn main:app --reload --port 8000"

# 2. Frontend 시작
Write-Host "Starting Frontend Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host "✅ 모든 서버가 실행되었습니다!" -ForegroundColor Yellow
Write-Host "Backend: http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Press any key to exit this launcher (Servers will keep running)..."
Read-Host
