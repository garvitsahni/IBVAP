# IBVAP Demo Startup Script
# Starts all services: mediamtx, fusion server, edge pipeline, dashboard
# Run from project root: .\scripts\start_demo.ps1

param(
    [switch]$SkipMediaMTX,
    [switch]$SkipEdge,
    [switch]$NoDisplay
)

$ErrorActionPreference = "Continue"
$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "  IBVAP Demo Startup" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# 1. Start mediamtx (RTSP relay)
if (-not $SkipMediaMTX) {
    Write-Host "`n[1/4] Starting MediaMTX (RTSP relay)..." -ForegroundColor Yellow
    $existing = docker ps -q -f name=ibvap_mediamtx 2>$null
    if ($existing) {
        Write-Host "  MediaMTX already running" -ForegroundColor Gray
    } else {
        python "$projectRoot\scripts\setup_simulated_cameras.py"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  MediaMTX setup failed (Docker may not be running)" -ForegroundColor Red
            Write-Host "  Continuing without RTSP streams..." -ForegroundColor Yellow
        }
    }
}

# 2. Start PostgreSQL (if not running)
Write-Host "`n[2/4] Checking PostgreSQL..." -ForegroundColor Yellow
try {
    $pgStatus = & pg_isready -h 127.0.0.1 -p 5432 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  PostgreSQL is running" -ForegroundColor Gray
    } else {
        Write-Host "  Starting PostgreSQL..." -ForegroundColor Gray
        & net start postgresql-x64-16 2>$null
    }
} catch {
    Write-Host "  PostgreSQL check failed - ensure it's installed and running" -ForegroundColor Red
}

# 3. Start Fusion Server
Write-Host "`n[3/4] Starting Fusion Server..." -ForegroundColor Yellow
$fusionJob = Start-Job -ScriptBlock {
    Set-Location "$using:projectRoot"
    & "$using:projectRoot\venv\Scripts\python.exe" -m fusion_server.main
}
Write-Host "  Fusion server starting in background (PID: $($fusionJob.Id))" -ForegroundColor Gray
Start-Sleep -Seconds 3

# 4. Start Edge Pipeline
if (-not $SkipEdge) {
    Write-Host "`n[4/4] Starting Edge Pipeline..." -ForegroundColor Yellow
    $displayFlag = if ($NoDisplay) { "--no-display" } else { "" }
    $edgeJob = Start-Job -ScriptBlock {
        Set-Location "$using:projectRoot"
        & "$using:projectRoot\venv\Scripts\python.exe" -m edge.run_all --cameras cam1,cam2,cam3 --enable-face --enable-plate $using:displayFlag
    }
    Write-Host "  Edge pipeline starting in background (PID: $($edgeJob.Id))" -ForegroundColor Gray
} else {
    Write-Host "`n[4/4] Skipping Edge Pipeline" -ForegroundColor Gray
}

# 5. Build Dashboard (if needed)
Write-Host "`n[Bonus] Checking Dashboard build..." -ForegroundColor Yellow
$dashboardDist = "$projectRoot\dashboard\dist"
if (-not (Test-Path $dashboardDist)) {
    Write-Host "  Building dashboard..." -ForegroundColor Gray
    Push-Location "$projectRoot\dashboard"
    npm run build 2>$null
    Pop-Location
}

# Summary
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "  IBVAP Demo is starting!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "  Fusion Server API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  Dashboard:          http://127.0.0.1:8000/dashboard/" -ForegroundColor White
Write-Host "  Health Check:       http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "  MediaMTX RTSP:      rtsp://127.0.0.1:8554/cam1" -ForegroundColor Gray
Write-Host "  MediaMTX API:       http://127.0.0.1:9997" -ForegroundColor Gray
Write-Host ""
Write-Host "  To seed demo data:  python scripts/seed_demo_data.py" -ForegroundColor Yellow
Write-Host "  To stop:            Stop-Job *; Remove-Job *" -ForegroundColor Yellow
Write-Host ""

# Wait for server to be healthy
Write-Host "Waiting for server health check..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            Write-Host "  Server is healthy!" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if ($ready) {
    # Seed demo data
    Write-Host "`nSeeding demo data..." -ForegroundColor Yellow
    & "$projectRoot\venv\Scripts\python.exe" "$projectRoot\scripts\seed_demo_data.py"
}

Write-Host "`nDemo is ready. Open http://127.0.0.1:8000/dashboard/ in your browser." -ForegroundColor Green
