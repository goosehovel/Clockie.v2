============================================
WINDOWS KIOSK TOUCH KEYBOARD SETUP
============================================

This folder contains scripts to set up your Windows PC
to display the Wall Clock with touch keyboard support.

QUICK START:
------------
1. Right-click "enable-touch-keyboard.bat" and select
   "Run as administrator" (do this ONCE, then restart PC)

2. Edit "launch-clock-chrome.bat" or "launch-clock-edge.bat"
   to set your Pi's IP address (default: 192.168.0.19:8000)

3. Double-click the launcher to start the clock

AUTO-START ON BOOT:
-------------------
1. Press Win+R and type: shell:startup
2. Copy your preferred launcher (.bat file) to that folder
3. The clock will start automatically when Windows boots

TROUBLESHOOTING:
----------------
If the touch keyboard doesn't appear when you tap input fields:

1. Open Windows Settings
2. Go to: Time & Language > Typing
3. Turn ON: "Show the touch keyboard when not in tablet 
   mode and there's no keyboard attached"

4. Make sure your display is recognized as a touchscreen
   (check Device Manager > Human Interface Devices)

5. Try disconnecting any physical keyboard - Windows may
   be disabling the touch keyboard because one is connected

BROWSER FLAGS EXPLAINED:
------------------------
--kiosk              : Full screen, no browser UI
--enable-touch-events: Enable touch input handling  
--enable-pinch       : Enable pinch-to-zoom gestures
--touch-events=enabled: Force touch event support

FILES:
------
- enable-touch-keyboard.bat : Run once as admin to enable touch keyboard
- launch-clock-chrome.bat   : Start clock in Chrome kiosk mode
- launch-clock-edge.bat     : Start clock in Edge kiosk mode
- setup-touch-keyboard.ps1  : Full PowerShell setup script (optional)


