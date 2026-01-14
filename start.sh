#!/bin/bash
# Clockie Quick Start Script

set -e

echo "🕐 Clockie - Smart Wall Clock Dashboard"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📋 Creating .env from template..."
    cp env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your settings before continuing!"
    echo ""
    echo "   Required settings:"
    echo "   - WEATHER_API_KEY (get free at openweathermap.org)"
    echo "   - CALDAV_ACCOUNTS (for calendar sync)"
    echo ""
    echo "   Then run this script again."
    exit 1
fi

# Create config.json if it doesn't exist (for Spotify tokens persistence)
if [ ! -f "config.json" ]; then
    echo "{}" > config.json
    echo "📋 Created config.json for settings persistence"
fi

# Create notes directory if it doesn't exist
mkdir -p notes

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first:"
    echo "   curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# Check for docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Installing..."
    sudo apt-get update && sudo apt-get install -y docker-compose
fi

echo "🔨 Building Clockie..."
docker-compose build

echo ""
echo "🚀 Starting Clockie..."
docker-compose up -d

echo ""
echo "✅ Clockie is running!"
echo ""
echo "   📍 Access your clock at: http://$(hostname -I | awk '{print $1}'):8000"
echo "   📝 Edit notes at: http://$(hostname -I | awk '{print $1}'):8000/notes"
echo ""

# Check if Raspotify is set up
if ! systemctl --user is-active --quiet librespot 2>/dev/null; then
    echo "🎵 SPOTIFY SETUP"
    echo "   Want to play Spotify through your Pi's speakers?"
    echo ""
    read -p "   Set up Raspotify now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        chmod +x setup-raspotify.sh
        ./setup-raspotify.sh
    else
        echo "   Skipped. Run ./setup-raspotify.sh later if needed."
    fi
    echo ""
fi

echo "   Keyboard shortcuts:"
echo "   - Press 'T' to toggle light/dark mode"
echo "   - Press 'B' to cycle background themes"
echo "   - Press 'W' to toggle weather effects"
echo ""
echo "   View logs: docker-compose logs -f"
echo "   Stop: docker-compose down"
echo ""

