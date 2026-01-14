# 🕐 Clockie - Smart Wall Clock & Home Hub

A beautiful, modern wall clock dashboard with smart home integration. Designed for Raspberry Pi but runs anywhere with Python or Docker.

## ✨ Features

### Clock Dashboard
- **🌡️ Live Weather** - Real-time weather with day/night icons, moon phases, particle effects
- **📅 Multi-Calendar Sync** - Unified view from multiple iCloud accounts with recurring event support
- **📝 Sticky Notes** - Persistent notes with web editor
- **🤖 Jarvis AI** - Smart assistant integration
- **🎵 Spotify Integration** - Control playback via Raspotify
- **🎨 10+ Animated Themes** - Flowcean, Aurora, Nebula, Lava, Forest, and more
- **🎄 Holiday Themes** - Auto-activating themes for Christmas, Halloween, etc.
- **🌙 Auto Light/Dark** - Theme switches based on sunrise/sunset

### Home Hub (Zigbee Integration)
- **💡 Smart Lights** - Control Zigbee bulbs, switches, plugs
- **🌡️ Temperature Sensors** - Monitor temps throughout your home
- **🚪 Door/Window Sensors** - Track open/close status
- **📊 Temperature History** - SQLite-backed charts and analytics
- **🔌 Device Management** - Pair, rename, and configure devices

### AC Hub (HVAC Analytics)
- **❄️ Cycle Detection** - Automatic AC on/off detection
- **📈 Efficiency Metrics** - COP/EER calculations
- **💰 Cost Tracking** - Estimated energy costs
- **🌡️ Delta-T Monitoring** - Supply/return temperature differentials

### Nest Thermostat Integration
- **🪺 Google Nest Support** - View and control Nest thermostats
- **🌡️ Temperature Display** - Current temp, setpoint, humidity
- **🔄 Mode Control** - Heat, Cool, Heat-Cool, Off modes
- **📊 Real-time Sync** - Via Google SDM API

---

## 🚀 Quick Start

### Option 1: Raspberry Pi (Recommended)

```bash
# Clone the repository
git clone https://github.com/goosehovel/Clockie.v2.git
cd clockie/clockie_docker

# Run the installer
chmod +x install.sh
./install.sh
```

The installer will:
- Install Python dependencies
- Create a virtual environment
- Set up systemd service
- Configure auto-start on boot

### Option 2: Docker

```bash
# Clone and configure
git clone https://github.com/goosehovel/Clockie.v2.git
cd clockie/clockie_docker

# Copy and edit config
cp config.example.json config.json
nano config.json

# Start with Docker
docker-compose up -d
```

---

## ⚙️ Configuration

### Step 1: Copy the example config

```bash
cp config.example.json config.json
```

### Step 2: Edit config.json

```json
{
  "weather": {
    "api_key": "YOUR_OPENWEATHERMAP_API_KEY",
    "city": "Phoenix",
    "state": "AZ",
    "country": "US",
    "units": "imperial"
  },
  "calendar": {
    "update_interval": 300,
    "max_events": 500,
    "accounts": [
      {
        "name": "Personal",
        "url": "https://caldav.icloud.com",
        "username": "your-email@icloud.com",
        "password": "xxxx-xxxx-xxxx-xxxx"
      }
    ]
  },
  "spotify": {
    "client_id": "YOUR_SPOTIFY_CLIENT_ID",
    "client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
    "redirect_uri": "http://127.0.0.1:8000/api/spotify/callback"
  }
}
```

### Getting API Keys

| Service | How to Get |
|---------|-----------|
| **Weather** | Free at [openweathermap.org/api](https://openweathermap.org/api) |
| **iCloud Calendar** | App-specific password from [appleid.apple.com](https://appleid.apple.com/account/manage) → Security → App-Specific Passwords |
| **Spotify** | Create app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) |
| **Nest Thermostat** | See [Nest Setup section](#-google-nest-thermostat-setup-optional) below ($5 one-time fee) |

---

## 📱 Pages & URLs

| URL | Description |
|-----|-------------|
| `/` | Main clock dashboard |
| `/homehub` | Smart home device control |
| `/achub` | AC/HVAC analytics dashboard |
| `/upload` | Photo upload for clock background |
| `/notes` | Sticky notes editor |

---

## 🏠 Home Hub Setup (Zigbee)

To use smart home features, you need a Zigbee USB dongle and Zigbee2MQTT:

```bash
# Run the Zigbee setup script
chmod +x setup-zigbee2mqtt.sh
sudo ./setup-zigbee2mqtt.sh
```

This installs:
- Mosquitto MQTT broker
- Zigbee2MQTT
- Configures everything to work with Home Hub

**Supported Devices:**
- Zigbee bulbs (Philips Hue, IKEA, etc.)
- Smart plugs and switches
- Temperature/humidity sensors
- Door/window contact sensors
- Motion sensors

---

## 🎵 Spotify Setup (Optional)

Turn your Pi into a Spotify speaker:

```bash
./setup-raspotify.sh
```

Then in the clock settings:
1. Click ⚙️ Settings → Spotify
2. Enter your Client ID and Secret
3. Click "Connect Spotify"
4. Follow the authorization flow

Your Pi appears as "WallClock" in Spotify Connect!

---

## 🪺 Google Nest Thermostat Setup (Optional)

Clockie can display and control your Nest thermostat using the Google Smart Device Management (SDM) API.

### Prerequisites

- ✅ A Google (Gmail) account — **NOT** a Google Workspace account
- ✅ A Nest thermostat already added to your Google Home app
- ✅ One-time $5 USD registration fee to Google

### Step 1: Register for Google Device Access

1. Go to the [Device Access Console](https://console.nest.google.com/device-access)
2. Log in with the **same Google account** tied to your Nest devices
3. Accept the Terms of Service
4. Pay the one-time **$5 USD** registration fee

⚠️ **Important:** Make sure you're signed into the correct Google account — you can't change it later!

### Step 2: Create a Device Access Project

1. In the Device Access Console, click **Create Project**
2. Give it a name (e.g., "Clockie")
3. Skip the OAuth client ID for now (we'll add it next)
4. **Save your Project ID** — you'll need this!

### Step 3: Set Up Google Cloud OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Go to **APIs & Services** → **Library**
4. Search for **"Smart Device Management API"** and click **Enable**
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **OAuth Client ID**
7. Choose **Web application**
8. Add Authorized redirect URI:
   ```
   http://127.0.0.1:8000/api/integrations/nest/callback
   ```
   (Or use your Pi's IP: `http://YOUR_PI_IP:8000/api/integrations/nest/callback`)
9. **Save your Client ID and Client Secret**

### Step 4: Link OAuth to Device Access Project

1. Go back to the [Device Access Console](https://console.nest.google.com/device-access)
2. Open your project
3. Add the **OAuth Client ID** from Step 3

### Step 5: Configure Clockie

Add to your `config.json`:

```json
{
  "nest": {
    "project_id": "YOUR_DEVICE_ACCESS_PROJECT_ID",
    "client_id": "YOUR_OAUTH_CLIENT_ID",
    "client_secret": "YOUR_OAUTH_CLIENT_SECRET",
    "redirect_uri": "http://127.0.0.1:8000/api/integrations/nest/callback"
  }
}
```

### Step 6: Connect Your Nest Account

1. Open Clockie in your browser
2. Go to **Settings** → **Integrations** → **Nest**
3. Click **Connect Nest**
4. Sign in with your Google account
5. In the Partner Connections Manager, select your home and thermostat
6. Click **Allow**
7. You'll be redirected back to Clockie — done!

### Nest API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/integrations/nest/status` | Check connection status |
| `GET /api/integrations/nest/thermostat` | Get thermostat data |
| `GET /api/integrations/nest/devices` | List all Nest devices |
| `POST /api/integrations/nest/connect` | Start OAuth flow |
| `POST /api/integrations/nest/disconnect` | Disconnect account |

### Troubleshooting Nest

**"No devices found"**
- Make sure your Nest is in the Google Home app
- Verify you selected the device in Partner Connections Manager

**"Token expired"**
- Clockie auto-refreshes tokens, but if issues persist, disconnect and reconnect

**"Access denied"**
- Ensure you're using the same Google account for Device Access and Google Home
- Check that SDM API is enabled in Google Cloud Console

---

## 📁 Project Structure

```
clockie_docker/
├── backend_api.py          # FastAPI server (all APIs)
├── frontend/
│   ├── index.html          # Main clock UI
│   ├── homehub.html        # Smart home dashboard
│   ├── achub.html          # AC analytics dashboard
│   ├── upload.html         # Photo upload page
│   ├── styles.css          # All styles & themes
│   ├── app.js              # Frontend JavaScript
│   └── jarvis-avatar.png   # Jarvis icon
├── config.example.json     # Configuration template
├── requirements.txt        # Python dependencies
├── install.sh              # Raspberry Pi installer
├── setup-raspotify.sh      # Spotify speaker setup
├── setup-zigbee2mqtt.sh    # Zigbee/MQTT setup
├── docker-compose.yml      # Docker config
├── Dockerfile              # Container build
└── env.example             # Environment template
```

---

## 🔧 Requirements

### Python Dependencies
```
fastapi, uvicorn, aiofiles, websockets, requests, httpx,
caldav, python-dateutil, recurring-ical-events,
paho-mqtt, pillow, python-dotenv, lxml
```

### System Requirements
- Python 3.10+
- For Zigbee: USB Zigbee dongle + Node.js 18+
- For Spotify: Audio output (HDMI/3.5mm)

---

## 🐛 Troubleshooting

### Weather not loading
- Verify `api_key` in config.json is valid
- Check city/state spelling

### Calendar not syncing  
- Use app-specific password, not Apple ID password
- Verify JSON format is correct
- Check logs: `journalctl -u wallclock -f`

### Zigbee devices not showing
- Ensure Zigbee2MQTT is running: `systemctl status zigbee2mqtt`
- Check MQTT: `mosquitto_sub -t 'zigbee2mqtt/#' -v`

### Service won't start
```bash
# Check status
systemctl status wallclock

# View logs
journalctl -u wallclock -n 100

# Restart
sudo systemctl restart wallclock
```

---

## 📄 License

MIT License - feel free to use, modify, and share!

---

## 🙏 Credits

- Weather: [OpenWeatherMap](https://openweathermap.org/)
- Calendar: iCloud CalDAV
- Smart Home: [Zigbee2MQTT](https://www.zigbee2mqtt.io/)
- Built with [FastAPI](https://fastapi.tiangolo.com/) & ❤️
