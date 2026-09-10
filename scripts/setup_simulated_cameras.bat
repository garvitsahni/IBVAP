@echo off
REM IBVAP Phase 0: Simulated Camera Setup (Windows Batch)
REM Downloads test footage and starts mediamtx with 3 camera streams

set PROJECT_ROOT=%~dp0..
set FOOTAGE_DIR=%PROJECT_ROOT%\footage
set CONFIG_PATH=%PROJECT_ROOT%\mediamtx.yml

echo ============================================================
echo IBVAP Phase 0: Simulated Camera Setup
echo ============================================================

REM Create footage directory
if not exist "%FOOTAGE_DIR%" mkdir "%FOOTAGE_DIR%"

REM Check if test videos exist, if not create dummy ones using ffmpeg
for %%f in (cam1.mp4 cam2.mp4 cam3.mp4) do (
    if not exist "%FOOTAGE_DIR%\%%f" (
        echo Creating dummy video %%f...
        ffmpeg -f lavfi -i testsrc=duration=30:size=640x480:rate=30 -c:v libx264 -pix_fmt yuv420p -y "%FOOTAGE_DIR%\%%f" >nul 2>&1
        if errorlevel 1 (
            echo Failed to create %%f (ffmpeg not available?)
            type nul > "%FOOTAGE_DIR%\%%f"
        ) else (
            echo Created %%f
        )
    ) else (
        echo %%f already exists
    )
)

REM Generate mediamtx.yml
echo Generating mediamtx.yml...
(
echo # MediaMTX configuration for simulated multi-camera RTSP streams
echo paths:
echo   cam1:
echo     source: publisher
echo     sourceOnDemand: false
echo     runOnDemand: ffmpeg -re -stream_loop -1 -i /footage/cam1.mp4 -c copy -f rtsp rtsp://localhost:8554/cam1
echo     runOnDemandRestart: true
echo.
echo   cam2:
echo     source: publisher
echo     sourceOnDemand: false
echo     runOnDemand: ffmpeg -re -stream_loop -1 -i /footage/cam2.mp4 -c copy -f rtsp rtsp://localhost:8554/cam2
echo     runOnDemandRestart: true
echo.
echo   cam3:
echo     source: publisher
echo     sourceOnDemand: false
echo     runOnDemand: ffmpeg -re -stream_loop -1 -i /footage/cam3.mp4 -c copy -f rtsp rtsp://localhost:8554/cam3
echo     runOnDemandRestart: true
echo.
echo api:
echo   address: :9997
echo.
echo metrics:
echo   address: :9998
echo.
echo logLevel: info
echo logFormat: json
) > "%CONFIG_PATH%"

echo Generated mediamtx.yml

REM Stop existing mediamtx container if running
docker ps -q -f "name=ibvap_mediamtx" | findstr /r "." >nul
if not errorlevel 1 (
    echo Stopping existing mediamtx container...
    docker stop ibvap_mediamtx >nul 2>&1
    docker rm ibvap_mediamtx >nul 2>&1
)

REM Start mediamtx container
echo Starting mediamtx container...
docker run -d --name ibvap_mediamtx ^
    -p 8554:8554 -p 1935:1935 -p 8888:8888 ^
    -v "%CONFIG_PATH%:/mediamtx.yml" ^
    -v "%FOOTAGE_DIR%:/footage" ^
    bluenviron/mediamtx:latest /mediamtx.yml

if errorlevel 1 (
    echo Failed to start mediamtx container
    exit /b 1
)

echo mediamtx container started

REM Wait for RTSP port
echo Waiting for RTSP streams to be ready...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo RTSP URLs:
echo   cam1: rtsp://localhost:8554/cam1
echo   cam2: rtsp://localhost:8554/cam2
echo   cam3: rtsp://localhost:8554/cam3
echo.
echo MediaMTX API: http://localhost:9997
echo MediaMTX Metrics: http://localhost:9998
echo ============================================================
echo.
echo To view logs: docker logs -f ibvap_mediamtx
echo To stop: docker stop ibvap_mediamtx