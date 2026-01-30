# Web Source Code Visualization Dev Server
# Press [Q] to stop all servers

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Web Viz Dev Server"

Write-Host "[DEV] Starting Web Source Code Visualization Project..." -ForegroundColor Cyan

$root = Get-Location
$backendPath = Join-Path $root "backend"
$frontendPath = Join-Path $root "frontend"
$pythonExe = Join-Path $backendPath "venv\Scripts\python.exe"

$script:backendProc = $null
$script:frontendProc = $null

function Stop-AllServers {
    Write-Host "`n[STOP] Stopping all servers..." -ForegroundColor Yellow
    
    if ($script:backendProc -and !$script:backendProc.HasExited) {
        Write-Host "  Stopping: Backend (PID: $($script:backendProc.Id))" -ForegroundColor Gray
        Stop-Process -Id $script:backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    
    if ($script:frontendProc -and !$script:frontendProc.HasExited) {
        Write-Host "  Stopping: Frontend (PID: $($script:frontendProc.Id))" -ForegroundColor Gray
        Stop-Process -Id $script:frontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    
    Start-Sleep -Milliseconds 500
    @(8000, 3000) | ForEach-Object {
        $port = $_
        Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -ne "System") {
                Write-Host "  Cleanup: $($proc.ProcessName) (Port $port)" -ForegroundColor Gray
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -eq "" 
    } | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "[OK] All servers stopped." -ForegroundColor Green
}

# Check venv
if (-not (Test-Path $pythonExe)) {
    Write-Host "[WARN] Virtual environment not found. Creating..." -ForegroundColor Yellow
    Push-Location $backendPath
    & python -m venv venv
    & $pythonExe -m pip install -r requirements.txt
    Pop-Location
}

# Cleanup existing processes
Write-Host "[CLEAN] Cleaning up existing processes..." -ForegroundColor Gray
@(8000, 3000) | ForEach-Object {
    $port = $_
    Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

# Start Backend
Write-Host "[BE] Starting Backend Server..." -ForegroundColor Green
$script:backendProc = Start-Process -FilePath $pythonExe `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backendPath `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 2

# Start Frontend
Write-Host "[FE] Starting Frontend Server..." -ForegroundColor Green
$script:frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory $frontendPath `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "[OK] All servers are running!" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Backend API:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Frontend:     http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press [Q] to stop all servers." -ForegroundColor Magenta
Write-Host ""

try {
    while ($true) {
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq 'Q' -or $key.Key -eq 'Escape') {
                break
            }
        }
        
        if ($script:backendProc.HasExited -and $script:frontendProc.HasExited) {
            Write-Host "[WARN] All servers have stopped unexpectedly." -ForegroundColor Yellow
            break
        }
        
        Start-Sleep -Milliseconds 200
    }
}
finally {
    Stop-AllServers
}

Write-Host ""
Write-Host "[BYE] Dev server stopped." -ForegroundColor Cyan
