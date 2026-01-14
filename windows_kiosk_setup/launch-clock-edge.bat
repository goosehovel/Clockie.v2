@echo off
REM ============================================
REM Wall Clock Kiosk - Edge Launcher
REM Always loads fresh content (no cache)
REM ============================================

SET CLOCK_URL=http://192.168.0.19:8000

REM Clear Edge cache before starting (optional - uncomment if needed)
REM rd /s /q "%LOCALAPPDATA%\Edge_Kiosk\Default\Cache" 2>nul
REM rd /s /q "%LOCALAPPDATA%\Edge_Kiosk\Default\Code Cache" 2>nul

REM Start Edge in kiosk mode with cache disabled
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
    --kiosk ^
    --app=%CLOCK_URL% ^
    --start-fullscreen ^
    --noerrdialogs ^
    --disable-infobars ^
    --disable-session-crashed-bubble ^
    --enable-touch-events ^
    --enable-pinch ^
    --touch-events=enabled ^
    --disable-application-cache ^
    --disk-cache-size=1 ^
    --media-cache-size=1 ^
    --aggressive-cache-discard ^
    --disable-background-networking ^
    --disable-component-update ^
    --user-data-dir="%LOCALAPPDATA%\Edge_Kiosk"
