# FluxFuzzer Run Script
$ErrorActionPreference = "Stop"

function Cleanup {
    Write-Host "`n[!] Cleaning up..." -ForegroundColor Yellow
    if ($global:fuzzerProcess) {
        Stop-Process -Id $global:fuzzerProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "plob/cookie") {
        Push-Location "plob/cookie"
        docker-compose down -v
        Pop-Location
    }
    Write-Host "[+] Cleanup Complete." -ForegroundColor Green
}

try {
    Write-Host "[*] Starting FluxFuzzer Dev Environment..." -ForegroundColor Green
    
    # 1. Start Docker
    if (Test-Path "plob/cookie/docker-compose.yml") {
        Write-Host "    -> Starting Docker containers..."
        Push-Location "plob/cookie"
        docker-compose up -d --force-recreate
        Pop-Location
    }
    else {
        Write-Warning "Docker compose file not found. Skipping Docker setup."
    }

    # 2. Start Fuzzer
    Write-Host "    -> Starting Web Dashboard..."
    $global:fuzzerProcess = Start-Process -FilePath "go" -ArgumentList "run", "cmd/fluxfuzzer/main.go", "web" -PassThru -NoNewWindow
    
    # 3. Wait and Open Browser
    Write-Host "    -> Waiting for server (5s)..."
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:9090"
    
    Write-Host "[!] System Ready. Press CTRL+C to stop." -ForegroundColor Cyan
    
    while ($true) {
        if ($global:fuzzerProcess.HasExited) {
            throw "FluxFuzzer process exited unexpectedly."
        }
        Start-Sleep -Seconds 1
    }
}
catch {
    Write-Error $_
}
finally {
    Cleanup
}
