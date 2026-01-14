#!/bin/bash
# Raspotify Setup Script - One-click Spotify Connect for your Pi
# Run this ONCE on your Raspberry Pi to enable Spotify playback

set -e

echo "🎵 Raspotify Setup for Clockie"
echo "=============================="
echo ""

# Check if running on Pi
if ! grep -q "Raspberry Pi\|BCM" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  This doesn't appear to be a Raspberry Pi."
    echo "   Raspotify is designed for Pi hardware."
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install Raspotify if not present
if ! command -v librespot &> /dev/null; then
    echo "📦 Installing Raspotify..."
    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
else
    echo "✅ Raspotify already installed"
fi

# Stop system service (we'll use user service instead for PipeWire)
echo "🔧 Configuring for PipeWire audio..."
sudo systemctl stop raspotify 2>/dev/null || true
sudo systemctl disable raspotify 2>/dev/null || true

# Create user service
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/librespot.service << 'EOF'
[Unit]
Description=Librespot Spotify Client (WallClock)
After=pipewire.service sound.target

[Service]
ExecStart=/usr/bin/librespot --name WallClock --device-type speaker --enable-volume-normalisation --bitrate 320 --quiet
Restart=always
RestartSec=10
Environment=PULSE_SERVER=unix:/run/user/%U/pulse/native

[Install]
WantedBy=default.target
EOF

# Enable and start
echo "🚀 Starting Raspotify user service..."
systemctl --user daemon-reload
systemctl --user enable librespot
systemctl --user start librespot

# Enable linger so it starts on boot
sudo loginctl enable-linger $USER

# Verify it's running
sleep 2
if systemctl --user is-active --quiet librespot; then
    echo ""
    echo "✅ Raspotify is running!"
    echo ""
    echo "   Your Pi now appears as 'WallClock' in Spotify."
    echo ""
    echo "   To test:"
    echo "   1. Open Spotify on your phone"
    echo "   2. Tap the devices icon (speaker icon)"
    echo "   3. Select 'WallClock'"
    echo "   4. Play some music!"
    echo ""
    echo "   The clock app can now control playback."
else
    echo ""
    echo "❌ Raspotify failed to start. Check logs:"
    echo "   journalctl --user -u librespot -n 20"
fi

