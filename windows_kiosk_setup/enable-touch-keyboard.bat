@echo off
REM ============================================
REM Enable Windows Touch Keyboard for Kiosk
REM Run this as Administrator ONCE
REM ============================================

echo.
echo Enabling Touch Keyboard Service...
sc config TabletInputService start= auto
net start TabletInputService

echo.
echo Setting registry keys for auto-invoke...
reg add "HKCU\Software\Microsoft\TabletTip\1.7" /v EnableDesktopModeAutoInvoke /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Microsoft\TabletTip\1.7" /v TipbandDesiredVisibility /t REG_DWORD /d 1 /f

echo.
echo ============================================
echo Touch keyboard setup complete!
echo ============================================
echo.
echo IMPORTANT: Restart your PC for changes to take effect.
echo.
echo If keyboard still doesn't appear when tapping inputs:
echo 1. Go to Settings ^> Time ^& Language ^> Typing
echo 2. Turn ON "Show the touch keyboard when not in tablet mode
echo    and there's no keyboard attached"
echo.
pause


