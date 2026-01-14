# ============================================
# Windows Kiosk Touch Keyboard Setup Script
# Run this as Administrator on the kiosk PC
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Touch Keyboard Setup for Kiosk Mode  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Enable and start the Touch Keyboard Service
Write-Host "[1/4] Configuring Touch Keyboard Service..." -ForegroundColor Yellow
$service = Get-Service -Name "TabletInputService" -ErrorAction SilentlyContinue
if ($service) {
    Set-Service -Name "TabletInputService" -StartupType Automatic
    Start-Service -Name "TabletInputService" -ErrorAction SilentlyContinue
    Write-Host "  ✓ TabletInputService enabled and started" -ForegroundColor Green
} else {
    Write-Host "  ⚠ TabletInputService not found (may not be a touch device)" -ForegroundColor Yellow
}

# 2. Set registry keys for touch keyboard auto-invoke
Write-Host ""
Write-Host "[2/4] Setting registry keys for auto-invoke..." -ForegroundColor Yellow

# Create the registry path if it doesn't exist
$regPath = "HKCU:\Software\Microsoft\TabletTip\1.7"
if (!(Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

# Enable auto-invoke for touch keyboard
Set-ItemProperty -Path $regPath -Name "EnableDesktopModeAutoInvoke" -Value 1 -Type DWord
Set-ItemProperty -Path $regPath -Name "TipbandDesiredVisibility" -Value 1 -Type DWord
Write-Host "  ✓ Touch keyboard auto-invoke enabled" -ForegroundColor Green

# Also set the system-wide setting
$regPathSystem = "HKLM:\SOFTWARE\Microsoft\TabletTip\1.7"
if (Test-Path $regPathSystem) {
    try {
        Set-ItemProperty -Path $regPathSystem -Name "EnableDesktopModeAutoInvoke" -Value 1 -Type DWord -ErrorAction SilentlyContinue
        Write-Host "  ✓ System-wide setting applied" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Could not set system-wide setting (requires admin)" -ForegroundColor Yellow
    }
}

# 3. Create browser launch scripts
Write-Host ""
Write-Host "[3/4] Creating browser launch scripts..." -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$clockUrl = Read-Host "Enter the clock URL (e.g., http://192.168.0.19:8000)"
if ([string]::IsNullOrWhiteSpace($clockUrl)) {
    $clockUrl = "http://192.168.0.19:8000"
}

# Chrome kiosk launcher
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$chromeScript = @"
@echo off
REM Wall Clock Kiosk - Chrome Launcher
REM Run this to start the clock in kiosk mode with touch support

start "" "$chromePath" ^
    --kiosk ^
    --app=$clockUrl ^
    --start-fullscreen ^
    --noerrdialogs ^
    --disable-infobars ^
    --disable-session-crashed-bubble ^
    --enable-touch-events ^
    --enable-pinch ^
    --touch-events=enabled ^
    --enable-features=TouchpadAndWheelScrollLatching,AsyncWheelEvents ^
    --disable-background-timer-throttling ^
    --disable-backgrounding-occluded-windows
"@

$chromeBatchPath = Join-Path $scriptDir "launch-clock-chrome.bat"
$chromeScript | Out-File -FilePath $chromeBatchPath -Encoding ASCII
Write-Host "  ✓ Created: launch-clock-chrome.bat" -ForegroundColor Green

# Edge kiosk launcher (often pre-installed on Windows)
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$edgeScript = @"
@echo off
REM Wall Clock Kiosk - Edge Launcher
REM Run this to start the clock in kiosk mode with touch support

start "" "$edgePath" ^
    --kiosk ^
    --app=$clockUrl ^
    --start-fullscreen ^
    --noerrdialogs ^
    --disable-infobars ^
    --disable-session-crashed-bubble ^
    --enable-touch-events ^
    --enable-pinch ^
    --touch-events=enabled ^
    --enable-features=TouchpadAndWheelScrollLatching,AsyncWheelEvents ^
    --disable-background-timer-throttling ^
    --disable-backgrounding-occluded-windows
"@

$edgeBatchPath = Join-Path $scriptDir "launch-clock-edge.bat"
$edgeScript | Out-File -FilePath $edgeBatchPath -Encoding ASCII
Write-Host "  ✓ Created: launch-clock-edge.bat" -ForegroundColor Green

# 4. Create auto-start shortcut (optional)
Write-Host ""
Write-Host "[4/4] Setup complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NEXT STEPS                           " -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Use one of these launchers to start the clock:" -ForegroundColor White
Write-Host "   - launch-clock-chrome.bat (if Chrome installed)" -ForegroundColor Gray
Write-Host "   - launch-clock-edge.bat (Edge is pre-installed)" -ForegroundColor Gray
Write-Host ""
Write-Host "2. To auto-start on boot:" -ForegroundColor White
Write-Host "   - Press Win+R, type: shell:startup" -ForegroundColor Gray
Write-Host "   - Copy the .bat file to that folder" -ForegroundColor Gray
Write-Host ""
Write-Host "3. If keyboard still doesn't appear:" -ForegroundColor White
Write-Host "   - Open Settings > Time & Language > Typing" -ForegroundColor Gray
Write-Host "   - Enable 'Show the touch keyboard when...'" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Restart this PC for all changes to take effect" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to exit"


