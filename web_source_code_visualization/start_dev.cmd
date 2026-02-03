@echo off
setlocal
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$Root = '%ROOT%'; $script = Get-Content -Raw '%~f0'; $marker = '#PS_' + 'START'; $idx = $script.IndexOf($marker); if ($idx -lt 0) { throw 'Marker not found' }; $script = $script.Substring($idx + $marker.Length); $sb = [ScriptBlock]::Create($script); $null = $sb.Invoke($Root)"
exit /b

#PS_START
param([string]$Root)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Web Source Code Visualization - Dev Server" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$FRONTEND_PORT = 10004
$BACKEND_PORT = 8000

# Step 1: Stop existing servers
Write-Host "[CLEAN] Stopping existing servers..." -ForegroundColor Yellow

$stopped = $false

# Kill backend (port 8000)
$backend = Get-NetTCPConnection -LocalPort $BACKEND_PORT -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($backend) {
    $backend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Backend (port $BACKEND_PORT) stopped" -ForegroundColor Green
    $stopped = $true
}

# Kill frontend (port 10004)
$frontend = Get-NetTCPConnection -LocalPort $FRONTEND_PORT -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($frontend) {
    $frontend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Frontend (port $FRONTEND_PORT) stopped" -ForegroundColor Green
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

# Step 2: Start frontend in background
Write-Host "[Frontend] Starting on port $FRONTEND_PORT..." -ForegroundColor Cyan

$frontendPath = Join-Path $Root "frontend"

# Check if node_modules exists
$nodeModules = Join-Path $frontendPath "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "  Installing dependencies (npm install)..." -ForegroundColor Yellow
    Push-Location $frontendPath
    npm install
    Pop-Location
}

# Start frontend in background (hidden window)
$frontendProcess = Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-WindowStyle", "Hidden",
    "-Command",
    "Set-Location '$frontendPath'; npm run dev"
) -WorkingDirectory $frontendPath -WindowStyle Hidden -PassThru

Write-Host "  Frontend running (PID: $($frontendProcess.Id))" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 3

# Step 3: Start backend in current terminal
Write-Host "========================================================" -ForegroundColor Green
Write-Host "[Backend] Starting on port $BACKEND_PORT..." -ForegroundColor Cyan
Write-Host ""
Write-Host "   Backend API:  http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host "   Frontend:     http://localhost:$FRONTEND_PORT" -ForegroundColor White
Write-Host ""
Write-Host "   Backend logs will appear below" -ForegroundColor Yellow
Write-Host "   Press Ctrl+C to stop (frontend will auto-close)" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

$backendPath = Join-Path $Root "backend"
Set-Location $backendPath

function Test-VenvPython([string]$PythonPath) {
    if (-not (Test-Path $PythonPath)) { return $false }
    try {
        & $PythonPath -c "import sys" *> $null
        if ($LASTEXITCODE -ne 0) { return $false }
        return $true
    } catch {
        return $false
    }
}

$venvDir = Join-Path $backendPath "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $backendPath "requirements.txt"

if (-not (Test-VenvPython $venvPython)) {
    Write-Host "[Backend] Virtualenv missing or broken. Rebuilding..." -ForegroundColor Yellow
    if (Test-Path $venvDir) {
        Remove-Item -Recurse -Force $venvDir
    }

    try {
        $basePython = (Get-Command python -ErrorAction Stop).Source
    } catch {
        Write-Host "[ERROR] Python not found in PATH. Install Python and retry." -ForegroundColor Red
        throw
    }

    & $basePython -m venv $venvDir
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r $requirements
}

try {
    & $venvPython -m uvicorn main:app --reload --host 127.0.0.1 --port $BACKEND_PORT
}
finally {
    Write-Host ""
    Write-Host "[SHUTDOWN] Stopping frontend..." -ForegroundColor Yellow
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] All servers stopped" -ForegroundColor Green
}
