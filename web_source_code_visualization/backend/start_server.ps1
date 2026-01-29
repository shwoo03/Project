# Backend Server Startup Script
# Ensures all dependencies are installed and starts the server

Write-Host "================================" -ForegroundColor Cyan
Write-Host " Backend Server Startup" -ForegroundColor Cyan  
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BackendDir

Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] Installing dependencies..." -ForegroundColor Yellow  
pip install --quiet fastapi uvicorn pyyaml python-dotenv tree-sitter requests pydantic
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Some packages may have failed to install" -ForegroundColor Yellow
}

Write-Host "[3/4] Setting environment..." -ForegroundColor Yellow
$env:PYTHONPATH = $BackendDir

Write-Host "[4/4] Starting server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host " Server starting on http://localhost:8000" -ForegroundColor Green
Write-Host " Press Ctrl+C to stop" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

# Start server
python -m uvicorn main:app --host 127.0.0.1 --port 8000
