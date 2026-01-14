#!/bin/bash
# Wait for the backend to start
sleep 10

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor after 0.5 seconds of inactivity
unclutter -idle 0.5 -root &

# Start the virtual keyboard (squeekboard) for touchscreen input
# Kill any existing instances first
pkill squeekboard 2>/dev/null
sleep 1

# Start squeekboard - it will show when text input is focused
squeekboard &
echo 'Started squeekboard virtual keyboard'

# Kill any existing Chromium instances
pkill chromium-browser

# Launch Chromium in kiosk mode with virtual keyboard support
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --app=http://localhost:8000 \
    --start-fullscreen \
    --window-position=0,0 \
    --window-size=1920,1080 \
    --enable-features=VirtualKeyboard,UseOzonePlatform \
    --ozone-platform=wayland \
    --enable-wayland-ime \
    --gtk-version=4
