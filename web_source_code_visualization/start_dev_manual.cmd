@echo off
setlocal
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$Root = '%ROOT%'; $script = Get-Content -Raw '%~f0'; $marker = '#PS_' + 'START'; $idx = $script.IndexOf($marker); if ($idx -lt 0) { throw 'Marker not found in start_dev_manual.cmd' }; $script = $script.Substring($idx + $marker.Length); $sb = [ScriptBlock]::Create($script); $null = $sb.Invoke($Root)"
exit /b

#PS_START
param([string]$Root)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Web Source Code Visualization - Dev Server" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[CLEAN] Stopping existing servers..." -ForegroundColor Yellow

$stopped = $false

$backend = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($backend) {
    $backend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Backend (port 8000) stopped" -ForegroundColor Green
    $stopped = $true
}

$frontend = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($frontend) {
    $frontend | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Write-Host "  Frontend (port 3000) stopped" -ForegroundColor Green
    $stopped = $true
}

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

Write-Host "[Frontend] Starting on port 3000..." -ForegroundColor Cyan

$frontendPath = Join-Path $Root "frontend"
$frontendProcess = Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "npm run dev" -WindowStyle Hidden -PassThru -WorkingDirectory $frontendPath

Write-Host "  Frontend running (PID: $($frontendProcess.Id))" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2

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
$venvPython = Join-Path $venvDir "Scripts\\python.exe"
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
    & $venvPython -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
}
finally {
    Write-Host ""
    Write-Host "[SHUTDOWN] Stopping frontend..." -ForegroundColor Yellow
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] All servers stopped" -ForegroundColor Green
}
