#!/usr/bin/env python3
"""
FastAPI Backend for Wall Clock
Separates data logic from UI rendering
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
import shutil
import uuid
from PIL import Image, ImageOps
import io
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import secrets
import urllib.parse
import base64

# Import your existing data modules
import requests
import math
from typing import Dict, List, Optional

# ============================================================================
# CONFIGURATION (from your existing Config class)
# ============================================================================

class Config:
    """Configuration settings"""
    # Weather Settings - loaded from config.json
    WEATHER_API_KEY = ""  # Set via config.json
    WEATHER_CITY = "Phoenix"
    WEATHER_STATE = "AZ"
    WEATHER_COUNTRY = "US"
    WEATHER_UNITS = "imperial"
    WEATHER_UPDATE_INTERVAL = 600  # 10 minutes

    # Calendar Settings - loaded from config.json
    CALDAV_ACCOUNTS = []  # Set via config.json
    CALENDAR_UPDATE_INTERVAL = 300  # 5 minutes
    MAX_EVENTS_DISPLAY = 500

    # Sticky Note Settings
    STICKY_NOTE_FILE_PATH = Path("/home/admin/ClockNotes/ClockNote.txt")
    STICKY_NOTE_UPDATE_INTERVAL = 60  # 1 minute

    # Spotify Settings
    SPOTIFY_CLIENT_ID = ""  # Set via config.json or env
    SPOTIFY_CLIENT_SECRET = ""  # Set via config.json or env
    SPOTIFY_REDIRECT_URI = "http://localhost:8000/api/spotify/callback"  # Update for your setup
    # Scopes: streaming = Web Playback SDK, user-read-email = user profile, playback-state = see what's playing
    SPOTIFY_SCOPES = "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing"
    
    # Spotify tokens (stored in config.json, loaded at runtime)
    SPOTIFY_ACCESS_TOKEN = ""
    SPOTIFY_REFRESH_TOKEN = ""
    SPOTIFY_TOKEN_EXPIRES_AT = 0
    SPOTIFY_USER_ID = ""
    SPOTIFY_CONNECTED = False

    # Google Nest (SDM API) Settings
    NEST_PROJECT_ID = ""  # Device Access Project ID from Google Cloud
    NEST_CLIENT_ID = ""  # OAuth Client ID
    NEST_CLIENT_SECRET = ""  # OAuth Client Secret
    NEST_REDIRECT_URI = "http://127.0.0.1:8000/api/integrations/nest/callback"
    NEST_ACCESS_TOKEN = ""
    NEST_REFRESH_TOKEN = ""
    NEST_TOKEN_EXPIRES_AT = 0
    NEST_CONNECTED = False
    NEST_LAST_SYNC = None

    # Logging
    LOG_LEVEL = logging.INFO
    
    # Jarvis AI Agent Settings
    JARVIS_ENABLED = True
    JARVIS_UPDATE_INTERVAL = 1800  # 30 minutes
    FERRETBOX_API_URL = "http://192.168.0.82:8000"
    JARVIS_MODEL = "gpt-oss:20b"  # Default model to use

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA FETCHERS (Refactored from your existing code)
# ============================================================================

class WeatherFetcher:
    """Fetch weather data from OpenWeatherMap API"""

    def __init__(self):
        self.api_key = Config.WEATHER_API_KEY
        # Build full location string: "City,State,Country" for accurate results
        self.location = f"{Config.WEATHER_CITY},{Config.WEATHER_STATE},{Config.WEATHER_COUNTRY}"
        # Use full state name for display
        state_names = {"AZ": "Arizona", "IL": "Illinois", "IA": "Iowa", "CA": "California", "TX": "Texas", "NY": "New York", "FL": "Florida"}
        display_state = state_names.get(Config.WEATHER_STATE, Config.WEATHER_STATE)
        self.display_location = f"{Config.WEATHER_CITY}, {display_state}"
        self.units = Config.WEATHER_UNITS
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
        self.cache = None
        self.last_fetch = None

    def get_moon_phase(self) -> dict:
        """Calculate current moon phase"""
        from datetime import datetime
        import math
        
        # Known new moon date (Jan 6, 2000)
        known_new_moon = datetime(2000, 1, 6, 18, 14)
        now = datetime.now()
        
        # Lunar cycle is ~29.53 days
        lunar_cycle = 29.53058867
        days_since = (now - known_new_moon).total_seconds() / 86400
        current_cycle = days_since % lunar_cycle
        phase_percent = current_cycle / lunar_cycle
        
        # Determine phase name and emoji
        if phase_percent < 0.0625:
            return {'name': 'New Moon', 'emoji': '🌑', 'illumination': 0}
        elif phase_percent < 0.1875:
            return {'name': 'Waxing Crescent', 'emoji': '🌒', 'illumination': 25}
        elif phase_percent < 0.3125:
            return {'name': 'First Quarter', 'emoji': '🌓', 'illumination': 50}
        elif phase_percent < 0.4375:
            return {'name': 'Waxing Gibbous', 'emoji': '🌔', 'illumination': 75}
        elif phase_percent < 0.5625:
            return {'name': 'Full Moon', 'emoji': '🌕', 'illumination': 100}
        elif phase_percent < 0.6875:
            return {'name': 'Waning Gibbous', 'emoji': '🌖', 'illumination': 75}
        elif phase_percent < 0.8125:
            return {'name': 'Last Quarter', 'emoji': '🌗', 'illumination': 50}
        elif phase_percent < 0.9375:
            return {'name': 'Waning Crescent', 'emoji': '🌘', 'illumination': 25}
        else:
            return {'name': 'New Moon', 'emoji': '🌑', 'illumination': 0}

    def get_weather_icon(self, weather_id: int, is_night: bool = False) -> str:
        """Get emoji icon for weather condition, with day/night awareness"""
        # For clear skies, use sun/moon
        if weather_id == 800:
            if is_night:
                return self.get_moon_phase()['emoji']
            return "☀️"
        elif weather_id == 801:
            if is_night:
                return "🌙"  # Moon behind small cloud
            return "🌤️"
        elif weather_id == 802:
            return "⛅"
        elif weather_id in [803, 804]:
            return "☁️"
        # Weather conditions (same day/night)
        elif 200 <= weather_id < 300:
            return "⛈️"
        elif 300 <= weather_id < 400:
            return "🌦️"
        elif 500 <= weather_id < 600:
            return "🌧️" if weather_id != 511 else "🌨️"
        elif 600 <= weather_id < 700:
            return "❄️"
        elif 700 <= weather_id < 800:
            return "🌫️"
        return "🌡️"
    
    def get_weather_effect(self, weather_id: int, wind_speed: float = 0) -> str:
        """Determine what particle effect to show based on weather"""
        if 200 <= weather_id < 300:
            return "storm"  # Thunderstorm - rain + lightning
        elif 300 <= weather_id < 400:
            return "drizzle"  # Light rain
        elif 500 <= weather_id < 600:
            if weather_id == 511:
                return "snow"  # Freezing rain shows as snow
            return "rain"
        elif 600 <= weather_id < 700:
            return "snow"
        elif 700 <= weather_id < 800:
            return "fog"
        elif wind_speed > 20:  # Strong wind
            return "wind"
        return "none"

    async def fetch_weather(self) -> Dict:
        """Fetch current weather data"""
        # Return cache if fresh (< 10 minutes old)
        if self.cache and self.last_fetch:
            if (datetime.now() - self.last_fetch).seconds < Config.WEATHER_UPDATE_INTERVAL:
                return self.cache

        try:
            logger.info(f"Fetching weather for {self.location}")
            params = {
                'q': self.location,
                'appid': self.api_key,
                'units': self.units
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract weather information
            temp = round(data['main']['temp'])
            feels_like = round(data['main']['feels_like'])
            description = data['weather'][0]['description'].title()
            humidity = data['main']['humidity']
            weather_id = data['weather'][0]['id']
            wind_speed = data.get('wind', {}).get('speed', 0)
            
            # Get sunrise/sunset from API (Unix timestamps)
            now = datetime.now()
            sunrise_ts = data.get('sys', {}).get('sunrise', 0)
            sunset_ts = data.get('sys', {}).get('sunset', 0)
            
            # Determine if it's night using actual sunrise/sunset
            if sunrise_ts and sunset_ts:
                current_ts = now.timestamp()
                is_night = current_ts < sunrise_ts or current_ts > sunset_ts
                sunrise_time = datetime.fromtimestamp(sunrise_ts).strftime('%I:%M %p')
                sunset_time = datetime.fromtimestamp(sunset_ts).strftime('%I:%M %p')
            else:
                # Fallback to hour-based check
                hour = now.hour
                is_night = hour < 6 or hour >= 18
                sunrise_time = "6:00 AM"
                sunset_time = "6:00 PM"
            
            # Get appropriate icon based on day/night
            icon = self.get_weather_icon(weather_id, is_night)
            
            # Get moon phase for night display
            moon_phase = self.get_moon_phase()
            
            # Determine weather effect for particle system
            weather_effect = self.get_weather_effect(weather_id, wind_speed)

            self.cache = {
                'icon': icon,
                'temp': temp,
                'feels_like': feels_like,
                'description': description,
                'humidity': humidity,
                'weather_id': weather_id,
                'is_night': is_night,
                'sunrise': sunrise_time,
                'sunset': sunset_time,
                'wind_speed': wind_speed,
                'weather_effect': weather_effect,
                'moon_phase': moon_phase,
                'unit': '°F',
                'location': self.display_location,
                'last_update': datetime.now().isoformat()
            }

            self.last_fetch = datetime.now()
            logger.info(f"Weather updated: {description}, Night: {is_night}, Effect: {weather_effect}")
            return self.cache

        except Exception as e:
            logger.error(f"Weather fetch error: {e}")
            return {
                'icon': '❌',
                'temp': '--',
                'feels_like': '--',
                'description': 'Weather unavailable',
                'humidity': '--',
                'weather_id': 800,
                'is_night': False,
                'weather_effect': 'none',
                'moon_phase': {'name': 'Unknown', 'emoji': '🌙', 'illumination': 50},
                'unit': '°F',
                'location': self.display_location,
                'error': str(e)
            }


class CalendarFetcher:
    """Fetch events from multiple Apple Calendar accounts using CalDAV"""

    def __init__(self):
        self.accounts = Config.CALDAV_ACCOUNTS
        self.cache = []
        self.last_fetch = None

    def _fetch_from_account(self, account: Dict, now: datetime, end_date: datetime) -> List[Dict]:
        """Fetch events from a single CalDAV account with proper recurring event expansion"""
        import caldav
        from icalendar import Calendar
        import recurring_ical_events
        
        events_list = []
        account_name = account.get('name', 'Unknown')
        
        try:
            logger.info(f"Fetching from calendar account: {account_name}")
            
            client = caldav.DAVClient(
                url=account['url'],
                username=account['username'],
                password=account['password']
            )
            
            principal = client.principal()
            calendars = principal.calendars()
            
            for calendar in calendars:
                try:
                    # Fetch all events in the date range
                    events = calendar.date_search(start=now, end=end_date, expand=True)
                    
                    for event in events:
                        try:
                            # Get raw ical data
                            ical_data = event.data
                            ical_calendar = Calendar.from_ical(ical_data)
                            
                            # Use recurring_ical_events to expand recurring events
                            expanded_events = recurring_ical_events.of(ical_calendar).between(now, end_date)
                            
                            for vevent in expanded_events:
                                try:
                                    # Extract summary
                                    if hasattr(vevent, 'get') and vevent.get('SUMMARY'):
                                        raw_summary = str(vevent.get('SUMMARY'))
                                    elif hasattr(vevent, 'summary'):
                                        raw_summary = str(vevent.summary.value) if hasattr(vevent.summary, 'value') else str(vevent.summary)
                                    else:
                                        raw_summary = "Untitled Event"
                                    
                                    summary = ''.join(char for char in raw_summary
                                                    if ord(char) < 128 and (char.isprintable() or char == ' '))
                                    summary = ' '.join(summary.split())
                                    if len(summary) < 3:
                                        continue
                                    
                                    # Extract datetime - handle both dict-like and object-like access
                                    if hasattr(vevent, 'get') and vevent.get('DTSTART'):
                                        dtstart = vevent.get('DTSTART').dt
                                    elif hasattr(vevent, 'dtstart'):
                                        dtstart = vevent.dtstart.value if hasattr(vevent.dtstart, 'value') else vevent.dtstart
                                    else:
                                        continue
                                    
                                    if hasattr(dtstart, 'strftime'):
                                        if not hasattr(dtstart, 'hour'):
                                            from datetime import date as date_type
                                            if isinstance(dtstart, date_type):
                                                dtstart = datetime.combine(dtstart, datetime.min.time())
                                        
                                        if hasattr(dtstart, 'tzinfo') and dtstart.tzinfo is not None:
                                            dtstart = dtstart.replace(tzinfo=None)
                                        
                                        events_list.append({
                                            'title': summary,
                                            'datetime': dtstart.isoformat(),
                                            'date': dtstart.strftime("%b %d"),
                                            'time': dtstart.strftime("%I:%M %p"),
                                            'is_today': dtstart.date() == now.date(),
                                            'is_upcoming': dtstart.date() > now.date(),
                                            'account': account_name
                                        })
                                except Exception as e:
                                    logger.warning(f"Error parsing expanded event: {e}")
                                    continue
                                    
                        except Exception as e:
                            # Fall back to original method if expansion fails
                            try:
                                vevent = event.instance.vevent
                                
                                if hasattr(vevent, 'summary'):
                                    raw_summary = str(vevent.summary.value)
                                    summary = ''.join(char for char in raw_summary
                                                    if ord(char) < 128 and (char.isprintable() or char == ' '))
                                    summary = ' '.join(summary.split())
                                    if len(summary) < 3:
                                        continue
                                else:
                                    summary = "Untitled Event"
                                
                                dtstart = vevent.dtstart.value
                                
                                if hasattr(dtstart, 'strftime'):
                                    if not hasattr(dtstart, 'hour'):
                                        from datetime import date as date_type
                                        if isinstance(dtstart, date_type):
                                            dtstart = datetime.combine(dtstart, datetime.min.time())
                                    
                                    if hasattr(dtstart, 'tzinfo') and dtstart.tzinfo is not None:
                                        dtstart = dtstart.replace(tzinfo=None)
                                    
                                    events_list.append({
                                        'title': summary,
                                        'datetime': dtstart.isoformat(),
                                        'date': dtstart.strftime("%b %d"),
                                        'time': dtstart.strftime("%I:%M %p"),
                                        'is_today': dtstart.date() == now.date(),
                                        'is_upcoming': dtstart.date() > now.date(),
                                        'account': account_name
                                    })
                            except Exception as e2:
                                logger.warning(f"Error parsing event (fallback): {e2}")
                                continue
                except Exception as e:
                    logger.warning(f"Error fetching from calendar: {e}")
                    continue
                    
            logger.info(f"Found {len(events_list)} events from {account_name}")
            
        except Exception as e:
            logger.error(f"Error connecting to {account_name}: {e}")
            
        return events_list

    async def fetch_events(self) -> List[Dict]:
        """Fetch upcoming calendar events from all accounts"""
        # Return cache if fresh
        if self.cache and self.last_fetch:
            if (datetime.now() - self.last_fetch).seconds < Config.CALENDAR_UPDATE_INTERVAL:
                return self.cache

        try:
            import caldav
            
            all_events = []
            now = datetime.now()
            end_date = now + timedelta(days=365)
            
            # Fetch from all configured accounts
            for account in self.accounts:
                if account.get('username') and account.get('password'):
                    account_events = self._fetch_from_account(account, now, end_date)
                    all_events.extend(account_events)
            
            # Merge local quick-add events
            try:
                local_events_file = Path("/home/admin/ClockNotes/quick_events.json")
                if local_events_file.exists():
                    with open(local_events_file, 'r') as f:
                        local_events = json.load(f)
                        # Filter future/today events and add them
                        for event in local_events:
                            event_dt = datetime.fromisoformat(event['datetime'])
                            if event_dt.date() >= now.date():
                                # Update is_today/is_upcoming flags
                                event['is_today'] = event_dt.date() == now.date()
                                event['is_upcoming'] = event_dt.date() > now.date()
                                all_events.append(event)
                        logger.info(f"Merged {len(local_events)} local events")
            except Exception as e:
                logger.warning(f"Error loading local events: {e}")
            
            # Sort by datetime (unified view)
            all_events.sort(key=lambda x: x['datetime'])
            
            # Remove duplicates (same title + same datetime)
            seen = set()
            unique_events = []
            for event in all_events:
                key = (event['title'], event['datetime'])
                if key not in seen:
                    seen.add(key)
                    unique_events.append(event)
            
            # Limit events
            self.cache = unique_events[:Config.MAX_EVENTS_DISPLAY]
            self.last_fetch = datetime.now()
            
            logger.info(f"Total unified events: {len(self.cache)}")
            return self.cache

        except ImportError:
            logger.error("caldav module not installed")
            return []
        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []


class StickyNoteFetcher:
    """Fetch and save sticky note content"""

    def __init__(self):
        self.file_path = Config.STICKY_NOTE_FILE_PATH
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def fetch_note(self) -> Dict:
        """Read sticky note from file"""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    'content': content,
                    'exists': True,
                    'last_modified': datetime.fromtimestamp(
                        self.file_path.stat().st_mtime
                    ).isoformat()
                }
            else:
                # Create empty file
                self.file_path.write_text('')
                return {
                    'content': '',
                    'exists': True,
                    'last_modified': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error reading sticky note: {e}")
            return {
                'content': f'Error reading note: {str(e)}',
                'exists': False,
                'error': str(e)
            }

    async def save_note(self, content: str) -> Dict:
        """Save sticky note to file"""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Sticky note saved successfully")
            return {
                'success': True,
                'message': 'Note saved successfully',
                'last_modified': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error saving sticky note: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# ============================================================================
# SPOTIFY INTEGRATION
# ============================================================================

class SpotifyManager:
    """Handle Spotify OAuth and API interactions"""
    
    SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
    SPOTIFY_API_BASE = "https://api.spotify.com/v1"
    
    # OAuth state storage (simple in-memory for single-user device)
    _oauth_state = None
    
    # Error codes for consistent error handling
    ERROR_CODES = {
        'not_connected': {'code': 'not_connected', 'message': 'Spotify is not connected. Please connect your account in Settings.'},
        'needs_reauth': {'code': 'needs_reauth', 'message': 'Spotify authorization expired. Please reconnect your account.'},
        'no_device': {'code': 'no_device', 'message': 'No active Spotify device found. Start playing on any device first.'},
        'playback_unavailable': {'code': 'playback_unavailable', 'message': 'Playback not available. You may need Spotify Premium.'},
        'token_expired': {'code': 'token_expired', 'message': 'Session expired. Attempting to refresh...'},
        'invalid_state': {'code': 'invalid_state', 'message': 'Invalid authorization state. Please try connecting again.'},
    }
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if Spotify credentials are configured"""
        return bool(Config.SPOTIFY_CLIENT_ID and Config.SPOTIFY_CLIENT_SECRET)
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Spotify is connected with valid tokens"""
        return bool(Config.SPOTIFY_REFRESH_TOKEN)
    
    @classmethod
    def get_auth_url(cls) -> str:
        """Generate Spotify OAuth authorization URL"""
        if not cls.is_configured():
            raise ValueError("Spotify client ID and secret must be configured")
        
        # Generate secure state parameter
        cls._oauth_state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': Config.SPOTIFY_CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
            'scope': Config.SPOTIFY_SCOPES,
            'state': cls._oauth_state,
            'show_dialog': 'true'  # Always show dialog for re-auth
        }
        
        return f"{cls.SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    
    @classmethod
    def validate_state(cls, state: str) -> bool:
        """Validate OAuth state parameter"""
        if not cls._oauth_state or state != cls._oauth_state:
            return False
        cls._oauth_state = None  # Clear after use
        return True
    
    @classmethod
    async def exchange_code(cls, code: str) -> Dict:
        """Exchange authorization code for tokens"""
        if not cls.is_configured():
            raise ValueError("Spotify client ID and secret must be configured")
        
        # Prepare auth header
        auth_header = base64.b64encode(
            f"{Config.SPOTIFY_CLIENT_ID}:{Config.SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        
        try:
            response = requests.post(
                cls.SPOTIFY_TOKEN_URL,
                headers={
                    'Authorization': f'Basic {auth_header}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': Config.SPOTIFY_REDIRECT_URI
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Spotify token exchange failed: {response.status_code}")
                return {'error': 'token_exchange_failed', 'details': response.text}
            
            token_data = response.json()
            
            # Store tokens
            Config.SPOTIFY_ACCESS_TOKEN = token_data.get('access_token', '')
            Config.SPOTIFY_REFRESH_TOKEN = token_data.get('refresh_token', '')
            Config.SPOTIFY_TOKEN_EXPIRES_AT = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            Config.SPOTIFY_CONNECTED = True
            
            # Get user profile
            user_profile = cls._get_user_profile()
            if user_profile:
                Config.SPOTIFY_USER_ID = user_profile.get('id', '')
            
            # Save to config file
            save_config_to_file()
            
            logger.info(f"Spotify connected: user {Config.SPOTIFY_USER_ID}")
            return {'success': True, 'user_id': Config.SPOTIFY_USER_ID}
            
        except Exception as e:
            logger.error(f"Spotify token exchange error: {e}")
            return {'error': 'token_exchange_error', 'details': str(e)}
    
    @classmethod
    def _get_user_profile(cls) -> Optional[Dict]:
        """Get current user's Spotify profile"""
        try:
            response = requests.get(
                f"{cls.SPOTIFY_API_BASE}/me",
                headers={'Authorization': f'Bearer {Config.SPOTIFY_ACCESS_TOKEN}'},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error getting Spotify profile: {e}")
        return None
    
    @classmethod
    def refresh_token(cls) -> bool:
        """Refresh the access token using refresh token"""
        if not Config.SPOTIFY_REFRESH_TOKEN:
            logger.error("No refresh token available")
            return False
        
        auth_header = base64.b64encode(
            f"{Config.SPOTIFY_CLIENT_ID}:{Config.SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        
        try:
            response = requests.post(
                cls.SPOTIFY_TOKEN_URL,
                headers={
                    'Authorization': f'Basic {auth_header}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': Config.SPOTIFY_REFRESH_TOKEN
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Spotify token refresh failed: {response.status_code}")
                return False
            
            token_data = response.json()
            Config.SPOTIFY_ACCESS_TOKEN = token_data.get('access_token', '')
            Config.SPOTIFY_TOKEN_EXPIRES_AT = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            
            # Some refreshes also return a new refresh token
            if 'refresh_token' in token_data:
                Config.SPOTIFY_REFRESH_TOKEN = token_data['refresh_token']
            
            save_config_to_file()
            logger.info("Spotify token refreshed")
            return True
            
        except Exception as e:
            logger.error(f"Spotify token refresh error: {e}")
            return False
    
    @classmethod
    def _ensure_valid_token(cls) -> bool:
        """Ensure we have a valid access token, refreshing if needed"""
        if not cls.is_connected():
            return False
        
        # Check if token is expired or about to expire (5 min buffer)
        if datetime.now().timestamp() >= Config.SPOTIFY_TOKEN_EXPIRES_AT - 300:
            return cls.refresh_token()
        
        return True
    
    @classmethod
    def _api_request(cls, method: str, endpoint: str, data: Dict = None, retry_on_401: bool = True) -> Dict:
        """Make an API request with automatic token refresh"""
        if not cls._ensure_valid_token():
            return {'error': cls.ERROR_CODES['not_connected']}
        
        try:
            url = f"{cls.SPOTIFY_API_BASE}{endpoint}"
            headers = {'Authorization': f'Bearer {Config.SPOTIFY_ACCESS_TOKEN}'}
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == 'PUT':
                headers['Content-Type'] = 'application/json'
                response = requests.put(url, headers=headers, json=data or {}, timeout=10)
            elif method.upper() == 'POST':
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, headers=headers, json=data or {}, timeout=10)
            else:
                return {'error': 'invalid_method'}
            
            # Handle 401 with token refresh retry
            if response.status_code == 401 and retry_on_401:
                if cls.refresh_token():
                    return cls._api_request(method, endpoint, data, retry_on_401=False)
                return {'error': cls.ERROR_CODES['needs_reauth']}
            
            # Handle 204 (no content - success for some endpoints)
            if response.status_code == 204:
                return {'success': True}
            
            # Handle 404 for playback (no active device)
            if response.status_code == 404:
                return {'error': cls.ERROR_CODES['no_device']}
            
            # Handle 403 (forbidden - usually premium required)
            if response.status_code == 403:
                return {'error': cls.ERROR_CODES['playback_unavailable']}
            
            if response.status_code >= 400:
                return {'error': {'code': 'api_error', 'message': f'Spotify API error: {response.status_code}'}}
            
            return response.json() if response.text else {'success': True}
            
        except requests.exceptions.Timeout:
            return {'error': {'code': 'timeout', 'message': 'Spotify request timed out'}}
        except Exception as e:
            logger.error(f"Spotify API error: {e}")
            return {'error': {'code': 'api_error', 'message': str(e)}}
    
    @classmethod
    def get_now_playing(cls) -> Dict:
        """Get currently playing track"""
        result = cls._api_request('GET', '/me/player/currently-playing')
        
        if 'error' in result:
            return result
        
        # No content = nothing playing
        if not result or result.get('success'):
            return {
                'is_playing': False,
                'track': None,
                'device': None
            }
        
        # Parse the response
        item = result.get('item', {})
        return {
            'is_playing': result.get('is_playing', False),
            'track': {
                'name': item.get('name', 'Unknown'),
                'artist': ', '.join(a.get('name', '') for a in item.get('artists', [])),
                'album': item.get('album', {}).get('name', ''),
                'image': item.get('album', {}).get('images', [{}])[0].get('url', ''),
                'duration_ms': item.get('duration_ms', 0),
                'uri': item.get('uri', ''),
                'id': item.get('id', '')
            },
            'progress_ms': result.get('progress_ms', 0),
            'device': {
                'name': result.get('device', {}).get('name', 'Unknown'),
                'type': result.get('device', {}).get('type', 'unknown'),
                'volume': result.get('device', {}).get('volume_percent', 0)
            }
        }
    
    @classmethod
    def get_devices(cls) -> Dict:
        """Get available playback devices"""
        result = cls._api_request('GET', '/me/player/devices')
        
        if 'error' in result:
            return result
        
        devices = result.get('devices', [])
        return {
            'devices': [
                {
                    'id': d.get('id'),
                    'name': d.get('name'),
                    'type': d.get('type'),
                    'is_active': d.get('is_active', False),
                    'volume': d.get('volume_percent', 0)
                }
                for d in devices
            ]
        }
    
    @classmethod
    def play(cls, device_id: str = None, uri: str = None, context_uri: str = None) -> Dict:
        """Start or resume playback"""
        data = {}
        if uri:
            data['uris'] = [uri]
        elif context_uri:
            data['context_uri'] = context_uri
        
        endpoint = '/me/player/play'
        if device_id:
            endpoint += f'?device_id={device_id}'
        
        return cls._api_request('PUT', endpoint, data if data else None)
    
    @classmethod
    def pause(cls) -> Dict:
        """Pause playback"""
        return cls._api_request('PUT', '/me/player/pause')
    
    @classmethod
    def next_track(cls) -> Dict:
        """Skip to next track"""
        return cls._api_request('POST', '/me/player/next')
    
    @classmethod
    def previous_track(cls) -> Dict:
        """Skip to previous track"""
        return cls._api_request('POST', '/me/player/previous')
    
    @classmethod
    def transfer_playback(cls, device_id: str, play: bool = True) -> Dict:
        """Transfer playback to a specific device"""
        return cls._api_request('PUT', '/me/player', {
            'device_ids': [device_id],
            'play': play
        })
    
    @classmethod
    def get_status(cls) -> Dict:
        """Get Spotify connection status"""
        if not cls.is_configured():
            return {
                'configured': False,
                'connected': False,
                'message': 'Spotify credentials not configured. Add Client ID and Secret in Settings.'
            }
        
        if not cls.is_connected():
            return {
                'configured': True,
                'connected': False,
                'message': 'Spotify not connected. Click Connect to link your account.'
            }
        
        # Get user profile
        profile = cls._get_user_profile()
        
        # Safely get user image (might be empty array)
        user_image = ''
        if profile:
            images = profile.get('images', [])
            if images and len(images) > 0:
                user_image = images[0].get('url', '')
        
        return {
            'configured': True,
            'connected': True,
            'user': {
                'id': Config.SPOTIFY_USER_ID,
                'display_name': profile.get('display_name', '') if profile else '',
                'image': user_image
            }
        }
    
    @classmethod
    def disconnect(cls):
        """Disconnect Spotify (clear tokens)"""
        Config.SPOTIFY_ACCESS_TOKEN = ""
        Config.SPOTIFY_REFRESH_TOKEN = ""
        Config.SPOTIFY_TOKEN_EXPIRES_AT = 0
        Config.SPOTIFY_USER_ID = ""
        Config.SPOTIFY_CONNECTED = False
        save_config_to_file()
        logger.info("Spotify disconnected")


# ============================================================================
# GOOGLE NEST INTEGRATION (SDM API)
# ============================================================================

class NestManager:
    """Handle Google Nest Smart Device Management API interactions"""
    
    NEST_AUTH_URL = "https://nestservices.google.com/partnerconnections/{project_id}/auth"
    GOOGLE_TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
    SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"
    
    # OAuth state storage
    _oauth_state = None
    
    # Error codes for consistent error handling
    ERROR_CODES = {
        'not_connected': {'code': 'not_connected', 'message': 'Nest is not connected. Please connect your account.'},
        'not_configured': {'code': 'not_configured', 'message': 'Nest credentials are not configured.'},
        'needs_reauth': {'code': 'needs_reauth', 'message': 'Nest authorization expired. Please reconnect.'},
        'no_devices': {'code': 'no_devices', 'message': 'No Nest thermostats found.'},
        'api_error': {'code': 'api_error', 'message': 'Error communicating with Nest API.'},
        'invalid_state': {'code': 'invalid_state', 'message': 'Invalid authorization state. Please try again.'},
    }
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if Nest credentials are configured"""
        return bool(Config.NEST_PROJECT_ID and Config.NEST_CLIENT_ID and Config.NEST_CLIENT_SECRET)
    
    @classmethod
    def is_connected(cls) -> bool:
        """Check if Nest is connected with valid tokens"""
        return bool(Config.NEST_REFRESH_TOKEN)
    
    @classmethod
    def get_status(cls) -> dict:
        """Get current Nest connection status"""
        return {
            'configured': cls.is_configured(),
            'connected': cls.is_connected(),
            'last_successful_sync': Config.NEST_LAST_SYNC,
            'error': None if cls.is_connected() else (
                cls.ERROR_CODES['not_configured'] if not cls.is_configured() 
                else cls.ERROR_CODES['not_connected']
            )
        }
    
    @classmethod
    def get_auth_url(cls) -> str:
        """Generate Google OAuth authorization URL for Nest SDM"""
        if not cls.is_configured():
            raise ValueError("Nest credentials must be configured")
        
        # Generate secure state parameter
        cls._oauth_state = secrets.token_urlsafe(32)
        
        # Build the Nest partner connection auth URL
        auth_url = cls.NEST_AUTH_URL.format(project_id=Config.NEST_PROJECT_ID)
        
        params = {
            'redirect_uri': Config.NEST_REDIRECT_URI,
            'access_type': 'offline',
            'prompt': 'consent',
            'client_id': Config.NEST_CLIENT_ID,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/sdm.service',
            'state': cls._oauth_state
        }
        
        return f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    @classmethod
    def validate_state(cls, state: str) -> bool:
        """Validate OAuth state parameter"""
        if not cls._oauth_state or state != cls._oauth_state:
            return False
        cls._oauth_state = None  # Clear after use
        return True
    
    @classmethod
    async def exchange_code(cls, code: str) -> dict:
        """Exchange authorization code for tokens"""
        if not cls.is_configured():
            return {'error': cls.ERROR_CODES['not_configured']}
        
        try:
            response = requests.post(
                cls.GOOGLE_TOKEN_URL,
                data={
                    'client_id': Config.NEST_CLIENT_ID,
                    'client_secret': Config.NEST_CLIENT_SECRET,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': Config.NEST_REDIRECT_URI
                },
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"Nest token exchange failed: {response.status_code} - {response.text}")
                return {'error': 'token_exchange_failed', 'details': response.text}
            
            token_data = response.json()
            
            # Store tokens
            Config.NEST_ACCESS_TOKEN = token_data.get('access_token', '')
            Config.NEST_REFRESH_TOKEN = token_data.get('refresh_token', '')
            Config.NEST_TOKEN_EXPIRES_AT = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            Config.NEST_CONNECTED = True
            Config.NEST_LAST_SYNC = datetime.now().isoformat()
            
            # Save to config file
            save_config_to_file()
            
            logger.info("Nest connected successfully")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Nest token exchange error: {e}")
            return {'error': 'token_exchange_error', 'details': str(e)}
    
    @classmethod
    def refresh_token(cls) -> bool:
        """Refresh the access token using refresh token"""
        if not Config.NEST_REFRESH_TOKEN:
            logger.error("No Nest refresh token available")
            return False
        
        try:
            response = requests.post(
                cls.GOOGLE_TOKEN_URL,
                data={
                    'client_id': Config.NEST_CLIENT_ID,
                    'client_secret': Config.NEST_CLIENT_SECRET,
                    'refresh_token': Config.NEST_REFRESH_TOKEN,
                    'grant_type': 'refresh_token'
                },
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"Nest token refresh failed: {response.status_code}")
                return False
            
            token_data = response.json()
            Config.NEST_ACCESS_TOKEN = token_data.get('access_token', '')
            Config.NEST_TOKEN_EXPIRES_AT = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            
            # Google sometimes returns a new refresh token
            if 'refresh_token' in token_data:
                Config.NEST_REFRESH_TOKEN = token_data['refresh_token']
            
            save_config_to_file()
            logger.info("Nest token refreshed")
            return True
            
        except Exception as e:
            logger.error(f"Nest token refresh error: {e}")
            return False
    
    @classmethod
    def _ensure_valid_token(cls) -> bool:
        """Ensure we have a valid access token, refreshing if needed"""
        if not cls.is_connected():
            return False
        
        # Check if token is expired or about to expire (5 min buffer)
        if datetime.now().timestamp() >= Config.NEST_TOKEN_EXPIRES_AT - 300:
            return cls.refresh_token()
        
        return True
    
    @classmethod
    def _api_request(cls, method: str, endpoint: str, retry_on_401: bool = True) -> dict:
        """Make an SDM API request with automatic token refresh"""
        if not cls._ensure_valid_token():
            return {'error': cls.ERROR_CODES['not_connected']}
        
        try:
            url = f"{cls.SDM_API_BASE}{endpoint}"
            headers = {'Authorization': f'Bearer {Config.NEST_ACCESS_TOKEN}'}
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            else:
                response = requests.request(method, url, headers=headers, timeout=15)
            
            if response.status_code == 401 and retry_on_401:
                # Try refreshing token
                if cls.refresh_token():
                    return cls._api_request(method, endpoint, retry_on_401=False)
                return {'error': cls.ERROR_CODES['needs_reauth']}
            
            if response.status_code == 200:
                Config.NEST_LAST_SYNC = datetime.now().isoformat()
                save_config_to_file()
                return response.json()
            else:
                logger.error(f"Nest API error: {response.status_code} - {response.text}")
                return {'error': cls.ERROR_CODES['api_error'], 'status_code': response.status_code}
                
        except requests.exceptions.Timeout:
            logger.error("Nest API request timed out")
            return {'error': {'code': 'timeout', 'message': 'Request timed out'}}
        except Exception as e:
            logger.error(f"Nest API error: {e}")
            return {'error': cls.ERROR_CODES['api_error'], 'details': str(e)}
    
    @classmethod
    def get_devices(cls) -> dict:
        """Get list of Nest devices"""
        if not cls.is_connected():
            return {'error': cls.ERROR_CODES['not_connected']}
        
        return cls._api_request('GET', f'/enterprises/{Config.NEST_PROJECT_ID}/devices')
    
    @classmethod
    def get_thermostat_data(cls) -> dict:
        """Get thermostat readings with normalized data structure"""
        if not cls.is_connected():
            return {'error': cls.ERROR_CODES['not_connected'], 'connected': False}
        
        devices_response = cls.get_devices()
        
        if 'error' in devices_response:
            return devices_response
        
        devices = devices_response.get('devices', [])
        
        # Find thermostats
        thermostats = []
        for device in devices:
            device_type = device.get('type', '')
            if 'THERMOSTAT' in device_type:
                thermostat = cls._normalize_thermostat(device)
                thermostats.append(thermostat)
        
        if not thermostats:
            return {'error': cls.ERROR_CODES['no_devices'], 'thermostats': []}
        
        return {
            'connected': True,
            'last_sync': Config.NEST_LAST_SYNC,
            'thermostats': thermostats
        }
    
    @classmethod
    def _normalize_thermostat(cls, device: dict) -> dict:
        """Normalize SDM device traits to a clean thermostat object"""
        traits = device.get('traits', {})
        
        # Extract device name
        device_name = device.get('name', '').split('/')[-1]
        custom_name = traits.get('sdm.devices.traits.Info', {}).get('customName', '')
        display_name = custom_name if custom_name else device_name[:8]
        
        # Temperature (SDM reports in Celsius)
        temp_trait = traits.get('sdm.devices.traits.Temperature', {})
        ambient_temp_c = temp_trait.get('ambientTemperatureCelsius')
        ambient_temp_f = round((ambient_temp_c * 9/5) + 32, 1) if ambient_temp_c is not None else None
        
        # Humidity
        humidity_trait = traits.get('sdm.devices.traits.Humidity', {})
        humidity = humidity_trait.get('ambientHumidityPercent')
        
        # HVAC Mode
        mode_trait = traits.get('sdm.devices.traits.ThermostatMode', {})
        hvac_mode = mode_trait.get('mode', 'UNKNOWN')  # HEAT, COOL, HEATCOOL, OFF
        available_modes = mode_trait.get('availableModes', [])
        
        # HVAC Status (what it's actively doing)
        hvac_trait = traits.get('sdm.devices.traits.ThermostatHvac', {})
        hvac_status = hvac_trait.get('status', 'UNKNOWN')  # HEATING, COOLING, OFF
        
        # Temperature setpoints
        setpoint_trait = traits.get('sdm.devices.traits.ThermostatTemperatureSetpoint', {})
        heat_setpoint_c = setpoint_trait.get('heatCelsius')
        cool_setpoint_c = setpoint_trait.get('coolCelsius')
        heat_setpoint_f = round((heat_setpoint_c * 9/5) + 32, 1) if heat_setpoint_c is not None else None
        cool_setpoint_f = round((cool_setpoint_c * 9/5) + 32, 1) if cool_setpoint_c is not None else None
        
        # Eco mode
        eco_trait = traits.get('sdm.devices.traits.ThermostatEco', {})
        eco_mode = eco_trait.get('mode', 'OFF')  # MANUAL_ECO, OFF
        eco_heat_c = eco_trait.get('heatCelsius')
        eco_cool_c = eco_trait.get('coolCelsius')
        eco_heat_f = round((eco_heat_c * 9/5) + 32, 1) if eco_heat_c is not None else None
        eco_cool_f = round((eco_cool_c * 9/5) + 32, 1) if eco_cool_c is not None else None
        
        # Fan
        fan_trait = traits.get('sdm.devices.traits.Fan', {})
        fan_timer_mode = fan_trait.get('timerMode', 'OFF')  # ON, OFF
        
        # Connectivity
        connectivity_trait = traits.get('sdm.devices.traits.Connectivity', {})
        connectivity_status = connectivity_trait.get('status', 'UNKNOWN')  # ONLINE, OFFLINE
        
        return {
            'device_id': device_name,
            'display_name': display_name,
            'ambient_temperature_f': ambient_temp_f,
            'ambient_temperature_c': ambient_temp_c,
            'humidity_percent': humidity,
            'hvac_mode': hvac_mode,
            'hvac_status': hvac_status,
            'available_modes': available_modes,
            'heat_setpoint_f': heat_setpoint_f,
            'cool_setpoint_f': cool_setpoint_f,
            'eco_mode': eco_mode,
            'eco_heat_f': eco_heat_f,
            'eco_cool_f': eco_cool_f,
            'fan_status': fan_timer_mode,
            'connectivity': connectivity_status,
            'is_online': connectivity_status == 'ONLINE'
        }
    
    @classmethod
    def disconnect(cls):
        """Disconnect Nest (clear tokens)"""
        # Optionally revoke token with Google
        if Config.NEST_ACCESS_TOKEN:
            try:
                requests.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': Config.NEST_ACCESS_TOKEN},
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Could not revoke Nest token: {e}")
        
        Config.NEST_ACCESS_TOKEN = ""
        Config.NEST_REFRESH_TOKEN = ""
        Config.NEST_TOKEN_EXPIRES_AT = 0
        Config.NEST_CONNECTED = False
        Config.NEST_LAST_SYNC = None
        save_config_to_file()
        logger.info("Nest disconnected")


# ============================================================================
# JARVIS AI AGENT - Family Household Assistant
# ============================================================================

class JarvisAgent:
    """
    Jarvis - Your family's AI household assistant.
    Provides contextual updates about weather, events, and daily life.
    Connects to FerretBox/Ollama for AI-powered messages.
    """
    
    def __init__(self):
        self.last_weather_condition = None
        self.last_weather_temp = None
        self.last_events_hash = None
        self.last_briefing = None
        self.last_briefing_time = None
        self.ferretbox_url = Config.FERRETBOX_API_URL
        self.enabled = Config.JARVIS_ENABLED
        
    def _get_time_of_day(self) -> str:
        """Get friendly time of day greeting"""
        hour = datetime.now().hour
        if hour < 6:
            return "night owl"
        elif hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        elif hour < 21:
            return "evening"
        else:
            return "night"
    
    def _hash_events(self, events: list) -> str:
        """Create a hash of events to detect changes"""
        if not events:
            return ""
        # Hash based on event titles and dates (not times to avoid spam)
        event_strs = [f"{e.get('title', '')}_{e.get('date', '')}" for e in events[:10]]
        return hash(tuple(event_strs))
    
    def _is_significant_weather_change(self, new_weather: dict) -> bool:
        """Check if weather changed significantly (not just temp fluctuation)"""
        if not new_weather or not self.last_weather_condition:
            return False
        
        new_condition = new_weather.get('description', '').lower()
        old_condition = self.last_weather_condition.lower()
        
        # Significant changes: rain starting, snow, storms, clearing up
        significant_conditions = ['rain', 'storm', 'snow', 'thunder', 'clear', 'sunny']
        
        for condition in significant_conditions:
            # Check if condition started or stopped
            old_has = condition in old_condition
            new_has = condition in new_condition
            if old_has != new_has:
                logger.info(f"Jarvis: Significant weather change detected: {old_condition} -> {new_condition}")
                return True
        
        return False
    
    def _is_event_change(self, events: list) -> bool:
        """Check if events changed (new event added, etc)"""
        new_hash = self._hash_events(events)
        if self.last_events_hash and new_hash != self.last_events_hash:
            logger.info("Jarvis: Event change detected")
            return True
        return False
    
    def _build_prompt(self, weather: dict, today_events: list, upcoming_events: list) -> str:
        """Build a contextual prompt for Jarvis"""
        time_of_day = self._get_time_of_day()
        now = datetime.now()
        
        # Format weather info
        weather_info = "No weather data available"
        if weather:
            temp = weather.get('temp', 'N/A')
            feels = weather.get('feels_like', temp)
            condition = weather.get('description', 'unknown')
            humidity = weather.get('humidity', 'N/A')
            weather_info = f"{temp}°F (feels like {feels}°F), {condition}, {humidity}% humidity"
        
        # Format today's events
        today_str = "No events today"
        if today_events:
            events_list = []
            for e in today_events[:5]:
                time_str = e.get('time', 'All day')
                events_list.append(f"- {e.get('title', 'Event')} at {time_str}")
            today_str = "\n".join(events_list)
        
        # Format upcoming events
        upcoming_str = "No upcoming events"
        if upcoming_events:
            events_list = []
            for e in upcoming_events[:3]:
                date_str = e.get('date', 'Soon')
                events_list.append(f"- {e.get('title', 'Event')} on {date_str}")
            upcoming_str = "\n".join(events_list)
        
        prompt = f"""You are Jarvis, the friendly AI assistant for this family's smart home wall clock. 
Your job is to give a brief, warm, casual update about the day. Keep it SHORT (2-3 sentences max).
Be friendly and use occasional emojis. Address the family warmly.

Current time: {now.strftime('%I:%M %p')} ({time_of_day})
Day: {now.strftime('%A, %B %d')}

Weather: {weather_info}

Today's Events:
{today_str}

Upcoming Events:
{upcoming_str}

Give a brief, friendly update. If there's something important coming up soon, mention it!
If the weather is notable (rain, very hot/cold), mention it casually.
Keep the tone warm and helpful, like a friendly family assistant.
Don't list everything - just highlight what's most relevant RIGHT NOW.
Response should be 2-3 short sentences only."""

        return prompt
    
    def _sync_check_ferretbox(self):
        """Synchronous FerretBox check (run in thread)"""
        response = requests.get(f"{self.ferretbox_url}/api/status", timeout=5)
        return response
    
    async def check_ferretbox_status(self) -> dict:
        """Check if FerretBox is reachable and get status"""
        try:
            response = await asyncio.to_thread(self._sync_check_ferretbox)
            if response.status_code == 200:
                return {"online": True, "data": response.json()}
            return {"online": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.warning(f"Jarvis: FerretBox not reachable: {e}")
            return {"online": False, "error": str(e)}
    
    async def generate_briefing(self, weather: dict, today_events: list, upcoming_events: list, force: bool = False) -> dict:
        """Generate a new Jarvis briefing"""
        if not self.enabled:
            return {"message": None, "source": "disabled"}
        
        # Check if we should generate (30 min interval or significant change)
        now = datetime.now()
        should_generate = force
        trigger_reason = "forced" if force else None
        
        # Check time interval (30 minutes)
        if self.last_briefing_time:
            minutes_since = (now - self.last_briefing_time).total_seconds() / 60
            if minutes_since >= 30:
                should_generate = True
                trigger_reason = "scheduled"
        else:
            should_generate = True
            trigger_reason = "initial"
        
        # Check for significant changes
        if self._is_significant_weather_change(weather):
            should_generate = True
            trigger_reason = "weather_change"
        
        if self._is_event_change(today_events + upcoming_events):
            should_generate = True
            trigger_reason = "event_change"
        
        # Update state tracking
        if weather:
            self.last_weather_condition = weather.get('description', '')
            self.last_weather_temp = weather.get('temp', 0)
        self.last_events_hash = self._hash_events(today_events + upcoming_events)
        
        if not should_generate and self.last_briefing:
            return {
                "message": self.last_briefing,
                "source": "cached",
                "generated_at": self.last_briefing_time.isoformat() if self.last_briefing_time else None
            }
        
        # Try to generate from FerretBox (run in thread to avoid blocking)
        try:
            prompt = self._build_prompt(weather, today_events, upcoming_events)
            
            def _sync_call():
                return requests.post(
                    f"{self.ferretbox_url}/api/chat",
                    json={"message": prompt},
                    timeout=300  # 5 minutes - FerretBox can be slow when busy
                )
            
            response = await asyncio.to_thread(_sync_call)
            
            if response.status_code == 200:
                data = response.json()
                message = data.get('response', '').strip()
                
                # Clean up the response (remove any system-like prefixes)
                if message.startswith("Jarvis:"):
                    message = message[7:].strip()
                
                self.last_briefing = message
                self.last_briefing_time = now
                
                logger.info(f"Jarvis: Generated new briefing (trigger: {trigger_reason})")
                return {
                    "message": message,
                    "source": "ferretbox",
                    "trigger": trigger_reason,
                    "generated_at": now.isoformat()
                }
            else:
                logger.error(f"Jarvis: FerretBox returned {response.status_code}")
                return self._get_fallback_message(weather, today_events)
                
        except requests.exceptions.Timeout:
            logger.warning("Jarvis: FerretBox request timed out")
            return self._get_fallback_message(weather, today_events)
        except Exception as e:
            logger.error(f"Jarvis: Error generating briefing: {e}")
            return self._get_fallback_message(weather, today_events)
    
    def _get_fallback_message(self, weather: dict, today_events: list) -> dict:
        """Generate a simple fallback message without AI"""
        time_of_day = self._get_time_of_day()
        now = datetime.now()
        
        parts = [f"Good {time_of_day}, fam! 👋"]
        
        if weather:
            temp = weather.get('temp', '')
            condition = weather.get('description', '').lower()
            if temp and condition:
                parts.append(f"It's {temp}°F and {condition} outside.")
        
        if today_events:
            next_event = today_events[0]
            event_time = next_event.get('time', '')
            event_title = next_event.get('title', 'something')
            if event_time:
                parts.append(f"Don't forget: {event_title} at {event_time}! 📅")
            else:
                parts.append(f"Today: {event_title} 📅")
        elif not today_events:
            parts.append("No events today - enjoy the free time! 🎉")
        
        message = " ".join(parts)
        
        return {
            "message": message,
            "source": "fallback",
            "generated_at": now.isoformat()
        }
    
    def get_current_briefing(self) -> dict:
        """Get the current cached briefing"""
        if self.last_briefing:
            return {
                "message": self.last_briefing,
                "source": "cached",
                "generated_at": self.last_briefing_time.isoformat() if self.last_briefing_time else None
            }
        return {
            "message": "Hey fam! 👋 Jarvis is warming up... I'll have an update for you shortly!",
            "source": "initializing",
            "generated_at": datetime.now().isoformat()
        }

# Initialize Jarvis
jarvis_agent = JarvisAgent()


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(title="Wall Clock API", version="2.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for CSS and JS
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Create and mount photos directory
PHOTOS_DIR = Path("photos")
PHOTOS_DIR.mkdir(exist_ok=True)
app.mount("/photos", StaticFiles(directory="photos"), name="photos")

# Photo settings
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB max
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
PHOTO_MAX_DIMENSION = 1920  # Resize large images to save space

# Initialize data fetchers
weather_fetcher = WeatherFetcher()
calendar_fetcher = CalendarFetcher()
note_fetcher = StickyNoteFetcher()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Serve the frontend HTML"""
    return FileResponse("frontend/index.html")

@app.get("/api/weather")
async def get_weather():
    """Get current weather data"""
    return await weather_fetcher.fetch_weather()

@app.get("/api/calendar")
async def get_calendar():
    """Get calendar events"""
    events = await calendar_fetcher.fetch_events()

    # Separate today and upcoming
    today_events = [e for e in events if e.get('is_today', False)]
    upcoming_events = [e for e in events if e.get('is_upcoming', False)]

    return {
        'today': today_events,
        'upcoming': upcoming_events,
        'all': events
    }

@app.get("/api/notes")
async def get_notes():
    """Get sticky note content"""
    return await note_fetcher.fetch_note()

@app.post("/api/notes")
async def save_notes(content: str = Form(...)):
    """Save sticky note content"""
    return await note_fetcher.save_note(content)

# ============================================================================
# JARVIS AI AGENT API
# ============================================================================

@app.get("/api/jarvis/status")
async def jarvis_status():
    """Check Jarvis and FerretBox status"""
    ferretbox_status = await jarvis_agent.check_ferretbox_status()
    return {
        "jarvis_enabled": jarvis_agent.enabled,
        "ferretbox": ferretbox_status,
        "last_briefing_time": jarvis_agent.last_briefing_time.isoformat() if jarvis_agent.last_briefing_time else None
    }

@app.get("/api/jarvis/briefing")
async def jarvis_briefing(force: bool = False):
    """Get current Jarvis briefing (or generate new one if force=True)"""
    # Get current data for context
    weather = await weather_fetcher.fetch_weather()
    events = await calendar_fetcher.fetch_events()
    
    today_events = [e for e in events if e.get('is_today', False)]
    upcoming_events = [e for e in events if e.get('is_upcoming', False)]
    
    # Generate or get cached briefing
    briefing = await jarvis_agent.generate_briefing(
        weather=weather,
        today_events=today_events,
        upcoming_events=upcoming_events,
        force=force
    )
    
    return briefing

@app.post("/api/jarvis/refresh")
async def jarvis_refresh():
    """Force refresh Jarvis briefing"""
    return await jarvis_briefing(force=True)

# ============================================================================
# QUICK ADD EVENTS (Local storage for quick touch-screen event entry)
# ============================================================================

LOCAL_EVENTS_FILE = Path("/home/admin/ClockNotes/quick_events.json")

def load_local_events():
    """Load locally stored quick events"""
    try:
        if LOCAL_EVENTS_FILE.exists():
            with open(LOCAL_EVENTS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading local events: {e}")
    return []

def save_local_events(events):
    """Save locally stored quick events"""
    try:
        LOCAL_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving local events: {e}")
        return False

@app.post("/api/events/add")
async def add_quick_event(request: Request):
    """Add a quick event from touch screen"""
    try:
        data = await request.json()
        
        title = data.get('title', '').strip()
        date_str = data.get('date', '')  # YYYY-MM-DD format
        time_str = data.get('time', '')  # HH:MM format
        notes = data.get('notes', '').strip()
        all_day = data.get('all_day', False)
        
        if not title or not date_str:
            return {'success': False, 'error': 'Title and date are required'}
        
        # Parse the date/time
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            if time_str:
                time_parts = time_str.split(':')
                event_date = event_date.replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1])
                )
        except ValueError as e:
            return {'success': False, 'error': f'Invalid date/time format: {e}'}
        
        # Create event object
        now = datetime.now()
        new_event = {
            'id': f"local_{datetime.now().timestamp()}",
            'title': title,
            'datetime': event_date.isoformat(),
            'date': event_date.strftime("%b %d"),
            'time': event_date.strftime("%I:%M %p") if not all_day else "All Day",
            'is_today': event_date.date() == now.date(),
            'is_upcoming': event_date.date() > now.date(),
            'notes': notes,
            'all_day': all_day,
            'source': 'local',
            'created_at': now.isoformat()
        }
        
        # Load existing events, add new one, save
        events = load_local_events()
        events.append(new_event)
        
        # Clean up past events (keep only future/today events)
        events = [e for e in events if datetime.fromisoformat(e['datetime']).date() >= now.date()]
        
        if save_local_events(events):
            # Clear calendar cache to include new event
            calendar_fetcher.cache = None
            calendar_fetcher.last_fetch = None
            
            logger.info(f"Added quick event: {title} on {date_str}")
            return {'success': True, 'event': new_event}
        else:
            return {'success': False, 'error': 'Failed to save event'}
            
    except Exception as e:
        logger.error(f"Error adding quick event: {e}")
        return {'success': False, 'error': str(e)}

@app.get("/api/events/local")
async def get_local_events():
    """Get locally stored quick events"""
    events = load_local_events()
    # Filter out past events
    now = datetime.now()
    events = [e for e in events if datetime.fromisoformat(e['datetime']).date() >= now.date()]
    return {'events': events}

@app.delete("/api/events/{event_id}")
async def delete_local_event(event_id: str):
    """Delete a locally stored event"""
    try:
        events = load_local_events()
        events = [e for e in events if e.get('id') != event_id]
        if save_local_events(events):
            # Clear calendar cache
            calendar_fetcher.cache = None
            calendar_fetcher.last_fetch = None
            return {'success': True}
        return {'success': False, 'error': 'Failed to save'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================================
# Spotify API
# ============================================================================

@app.get("/api/spotify/status")
async def spotify_status():
    """Get Spotify connection status"""
    return SpotifyManager.get_status()

@app.get("/api/spotify/connect")
async def spotify_connect():
    """Start Spotify OAuth flow - returns auth URL for manual flow"""
    if not SpotifyManager.is_configured():
        return {'error': 'not_configured', 'message': 'Configure Spotify Client ID and Secret first'}
    
    auth_url = SpotifyManager.get_auth_url()
    return {
        'auth_url': auth_url,
        'manual_flow': True,
        'instructions': 'Open the auth URL, authorize, then copy the FULL URL you get redirected to (it will show an error, that\'s OK) and paste it below.'
    }

@app.post("/api/spotify/manual-callback")
async def spotify_manual_callback(request: Request):
    """Handle manual OAuth callback - user pastes the redirect URL"""
    try:
        data = await request.json()
        callback_url = data.get('callback_url', '')
        
        if not callback_url:
            return {'error': 'missing_url', 'message': 'Please paste the callback URL'}
        
        # Parse the URL to extract code and state
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        error = params.get('error', [None])[0]
        
        if error:
            return {'error': 'auth_error', 'message': f'Authorization failed: {error}'}
        
        if not code:
            return {'error': 'no_code', 'message': 'No authorization code found in URL. Make sure you copied the full URL.'}
        
        # Validate state
        if not SpotifyManager.validate_state(state):
            # State might be expired, but let's try anyway for better UX
            logger.warning("OAuth state validation failed, proceeding anyway")
        
        # Exchange code for tokens
        result = await SpotifyManager.exchange_code(code)
        
        if 'error' in result:
            return {'error': result.get('error'), 'message': result.get('details', 'Failed to exchange code')}
        
        return {'success': True, 'message': 'Spotify connected successfully!', 'user_id': result.get('user_id')}
        
    except Exception as e:
        logger.error(f"Manual callback error: {e}")
        return {'error': 'processing_error', 'message': str(e)}

@app.get("/api/spotify/callback")
async def spotify_callback(code: str = None, state: str = None, error: str = None):
    """Handle Spotify OAuth callback"""
    # Handle OAuth errors
    if error:
        logger.error(f"Spotify OAuth error: {error}")
        return RedirectResponse(url="/?spotify_error=" + error)
    
    if not code:
        return RedirectResponse(url="/?spotify_error=no_code")
    
    # Validate state
    if not SpotifyManager.validate_state(state):
        logger.error("Invalid OAuth state")
        return RedirectResponse(url="/?spotify_error=invalid_state")
    
    # Exchange code for tokens
    result = await SpotifyManager.exchange_code(code)
    
    if 'error' in result:
        return RedirectResponse(url="/?spotify_error=" + result.get('error', 'unknown'))
    
    # Success - redirect back to main page
    return RedirectResponse(url="/?spotify_connected=true")

@app.post("/api/spotify/disconnect")
async def spotify_disconnect():
    """Disconnect Spotify account"""
    SpotifyManager.disconnect()
    return {'success': True, 'message': 'Spotify disconnected'}

@app.get("/api/spotify/token")
async def spotify_token():
    """Get access token for Web Playback SDK (frontend use)"""
    if not Config.SPOTIFY_CONNECTED and not Config.SPOTIFY_REFRESH_TOKEN:
        return {'error': 'not_connected', 'message': 'Spotify not connected'}
    
    # Ensure token is valid (will refresh if needed)
    if not SpotifyManager._ensure_valid_token():
        return {'error': 'token_expired', 'message': 'Failed to refresh token. Please reconnect.'}
    
    return {
        'access_token': Config.SPOTIFY_ACCESS_TOKEN,
        'expires_at': Config.SPOTIFY_TOKEN_EXPIRES_AT
    }

@app.get("/api/spotify/now-playing")
async def spotify_now_playing():
    """Get currently playing track"""
    return SpotifyManager.get_now_playing()

@app.get("/api/spotify/devices")
async def spotify_devices():
    """Get available Spotify devices (including Raspotify)"""
    return SpotifyManager.get_devices()

@app.post("/api/spotify/play")
async def spotify_play(request: Request):
    """Start or resume playback on active device"""
    try:
        data = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    except:
        data = {}
    
    return SpotifyManager.play(
        device_id=data.get('device_id'),
        uri=data.get('uri'),
        context_uri=data.get('context_uri')
    )

@app.post("/api/spotify/pause")
async def spotify_pause():
    """Pause playback"""
    return SpotifyManager.pause()

@app.post("/api/spotify/next")
async def spotify_next():
    """Skip to next track"""
    return SpotifyManager.next_track()

@app.post("/api/spotify/previous")
async def spotify_previous():
    """Skip to previous track"""
    return SpotifyManager.previous_track()

@app.post("/api/spotify/transfer")
async def spotify_transfer(request: Request):
    """Transfer playback to a specific device"""
    try:
        data = await request.json()
        device_id = data.get('device_id')
        if not device_id:
            return {'error': 'missing_device_id', 'message': 'Device ID required'}
        
        return SpotifyManager.transfer_playback(device_id)
    except Exception as e:
        return {'error': 'transfer_failed', 'message': str(e)}

# ============================================================================
# NEST INTEGRATION API
# ============================================================================

@app.get("/api/integrations/nest/status")
async def nest_status():
    """Get Nest connection status"""
    return NestManager.get_status()

@app.post("/api/integrations/nest/connect")
async def nest_connect():
    """Start Nest OAuth flow - returns auth URL"""
    if not NestManager.is_configured():
        return {
            'error': 'not_configured', 
            'message': 'Configure Nest Project ID, Client ID and Client Secret first',
            'help': 'Visit console.nest.google.com to create a Device Access project'
        }
    
    try:
        auth_url = NestManager.get_auth_url()
        return {
            'auth_url': auth_url,
            'instructions': 'Open the auth URL, authorize access, and you will be redirected back.'
        }
    except Exception as e:
        return {'error': 'auth_url_failed', 'message': str(e)}

@app.get("/api/integrations/nest/callback")
async def nest_callback(code: str = None, state: str = None, error: str = None):
    """Handle Nest OAuth callback"""
    if error:
        logger.error(f"Nest OAuth error: {error}")
        return RedirectResponse(url="/?nest_error=" + error)
    
    if not code:
        return RedirectResponse(url="/?nest_error=no_code")
    
    # Validate state
    if not NestManager.validate_state(state):
        logger.error("Invalid Nest OAuth state")
        return RedirectResponse(url="/?nest_error=invalid_state")
    
    # Exchange code for tokens
    result = await NestManager.exchange_code(code)
    
    if 'error' in result:
        return RedirectResponse(url="/?nest_error=" + str(result.get('error')))
    
    return RedirectResponse(url="/?nest_connected=true")

@app.post("/api/integrations/nest/disconnect")
async def nest_disconnect():
    """Disconnect Nest (clear tokens)"""
    NestManager.disconnect()
    return {'success': True, 'message': 'Nest disconnected'}

@app.get("/api/integrations/nest/thermostat")
async def nest_thermostat():
    """Get thermostat readings"""
    return NestManager.get_thermostat_data()

@app.get("/api/integrations/nest/devices")
async def nest_devices():
    """Get all Nest devices"""
    return NestManager.get_devices()

# ============================================================================
# Configuration API
# ============================================================================

CONFIG_FILE = Path("/home/admin/wallclock/config.json")

@app.get("/api/config")
async def get_config():
    """Get current configuration (with masked secrets)"""
    try:
        # Return current config from memory with partially masked secrets
        weather_config = {
            'api_key': mask_secret(Config.WEATHER_API_KEY),
            'city': Config.WEATHER_CITY,
            'state': Config.WEATHER_STATE,
            'country': Config.WEATHER_COUNTRY,
            'units': Config.WEATHER_UNITS
        }
        
        calendar_config = {
            'update_interval': Config.CALENDAR_UPDATE_INTERVAL,
            'max_events': Config.MAX_EVENTS_DISPLAY,
            'accounts': [
                {
                    'name': acc.get('name', 'Account'),
                    'url': acc.get('url', ''),
                    'username': acc.get('username', ''),
                    'password': mask_secret(acc.get('password', ''))
                }
                for acc in Config.CALDAV_ACCOUNTS
            ]
        }
        
        spotify_config = {
            'client_id': mask_secret(Config.SPOTIFY_CLIENT_ID),
            'client_secret': mask_secret(Config.SPOTIFY_CLIENT_SECRET),
            'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
            'connected': Config.SPOTIFY_CONNECTED,
            'user_id': Config.SPOTIFY_USER_ID
        }
        
        nest_config = {
            'project_id': mask_secret(Config.NEST_PROJECT_ID),
            'client_id': mask_secret(Config.NEST_CLIENT_ID),
            'client_secret': mask_secret(Config.NEST_CLIENT_SECRET),
            'redirect_uri': Config.NEST_REDIRECT_URI,
            'connected': Config.NEST_CONNECTED,
            'last_sync': Config.NEST_LAST_SYNC
        }
        
        return {
            'weather': weather_config,
            'calendar': calendar_config,
            'spotify': spotify_config,
            'nest': nest_config
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return {'error': str(e)}

@app.post("/api/config")
async def save_config(request: Request):
    """Save configuration"""
    global weather_fetcher, calendar_fetcher
    
    try:
        data = await request.json()
        
        # Update weather config
        if 'weather' in data:
            w = data['weather']
            if w.get('api_key') and not w['api_key'].startswith('••••'):
                Config.WEATHER_API_KEY = w['api_key']
            if w.get('city'):
                Config.WEATHER_CITY = w['city']
            if w.get('state'):
                Config.WEATHER_STATE = w['state']
            if w.get('country'):
                Config.WEATHER_COUNTRY = w['country']
            if w.get('units'):
                Config.WEATHER_UNITS = w['units']
        
        # Update calendar config
        if 'calendar' in data:
            c = data['calendar']
            if c.get('update_interval'):
                Config.CALENDAR_UPDATE_INTERVAL = c['update_interval']
            if c.get('max_events'):
                Config.MAX_EVENTS_DISPLAY = c['max_events']
            
            # Update accounts (only if password is not masked)
            if 'accounts' in c:
                new_accounts = []
                for acc in c['accounts']:
                    if acc.get('password') and not acc['password'].startswith('••••'):
                        # New password provided
                        new_accounts.append({
                            'name': acc.get('name', 'Account'),
                            'url': acc.get('url', 'https://caldav.icloud.com'),
                            'username': acc.get('username', ''),
                            'password': acc['password']
                        })
                    else:
                        # Try to preserve existing password
                        existing = next(
                            (a for a in Config.CALDAV_ACCOUNTS 
                             if a.get('username') == acc.get('username')),
                            None
                        )
                        if existing:
                            new_accounts.append({
                                'name': acc.get('name', existing.get('name', 'Account')),
                                'url': acc.get('url', existing.get('url', '')),
                                'username': acc.get('username', ''),
                                'password': existing.get('password', '')
                            })
                
                if new_accounts:
                    Config.CALDAV_ACCOUNTS = new_accounts
        
        # Update Spotify config
        if 'spotify' in data:
            s = data['spotify']
            if s.get('client_id') and not s['client_id'].startswith('••••'):
                Config.SPOTIFY_CLIENT_ID = s['client_id']
            if s.get('client_secret') and not s['client_secret'].startswith('••••'):
                Config.SPOTIFY_CLIENT_SECRET = s['client_secret']
            if s.get('redirect_uri'):
                Config.SPOTIFY_REDIRECT_URI = s['redirect_uri']
        
        # Update Nest config
        if 'nest' in data:
            n = data['nest']
            if n.get('project_id') and not n['project_id'].startswith('••••'):
                Config.NEST_PROJECT_ID = n['project_id']
            if n.get('client_id') and not n['client_id'].startswith('••••'):
                Config.NEST_CLIENT_ID = n['client_id']
            if n.get('client_secret') and not n['client_secret'].startswith('••••'):
                Config.NEST_CLIENT_SECRET = n['client_secret']
            if n.get('redirect_uri'):
                Config.NEST_REDIRECT_URI = n['redirect_uri']
        
        # Save to config file for persistence
        save_config_to_file()
        
        # Reinitialize fetchers with new config
        weather_fetcher = WeatherFetcher()
        calendar_fetcher = CalendarFetcher()
        
        # Clear caches to force refresh
        weather_fetcher.cache = None
        weather_fetcher.last_fetch = None
        calendar_fetcher.cache = []
        calendar_fetcher.last_fetch = None
        
        logger.info("Configuration updated successfully")
        return {'success': True, 'message': 'Configuration saved'}
        
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return {'success': False, 'error': str(e)}

def mask_secret(secret: str) -> str:
    """Mask a secret, showing only last 4 characters"""
    if not secret or len(secret) < 8:
        return '••••••••' if secret else ''
    return '••••••••' + secret[-4:]

def save_config_to_file():
    """Save current config to file for persistence across restarts"""
    try:
        config_data = {
            'weather': {
                'api_key': Config.WEATHER_API_KEY,
                'city': Config.WEATHER_CITY,
                'state': Config.WEATHER_STATE,
                'country': Config.WEATHER_COUNTRY,
                'units': Config.WEATHER_UNITS
            },
            'calendar': {
                'update_interval': Config.CALENDAR_UPDATE_INTERVAL,
                'max_events': Config.MAX_EVENTS_DISPLAY,
                'accounts': Config.CALDAV_ACCOUNTS
            },
            'spotify': {
                'client_id': Config.SPOTIFY_CLIENT_ID,
                'client_secret': Config.SPOTIFY_CLIENT_SECRET,
                'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
                'access_token': Config.SPOTIFY_ACCESS_TOKEN,
                'refresh_token': Config.SPOTIFY_REFRESH_TOKEN,
                'token_expires_at': Config.SPOTIFY_TOKEN_EXPIRES_AT,
                'user_id': Config.SPOTIFY_USER_ID,
                'connected': Config.SPOTIFY_CONNECTED
            },
            'nest': {
                'project_id': Config.NEST_PROJECT_ID,
                'client_id': Config.NEST_CLIENT_ID,
                'client_secret': Config.NEST_CLIENT_SECRET,
                'redirect_uri': Config.NEST_REDIRECT_URI,
                'access_token': Config.NEST_ACCESS_TOKEN,
                'refresh_token': Config.NEST_REFRESH_TOKEN,
                'token_expires_at': Config.NEST_TOKEN_EXPIRES_AT,
                'connected': Config.NEST_CONNECTED,
                'last_sync': Config.NEST_LAST_SYNC
            }
        }
        
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Config saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save config file: {e}")

def load_config_from_file():
    """Load config from file if it exists"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            
            if 'weather' in data:
                w = data['weather']
                Config.WEATHER_API_KEY = w.get('api_key', Config.WEATHER_API_KEY)
                Config.WEATHER_CITY = w.get('city', Config.WEATHER_CITY)
                Config.WEATHER_STATE = w.get('state', Config.WEATHER_STATE)
                Config.WEATHER_COUNTRY = w.get('country', Config.WEATHER_COUNTRY)
                Config.WEATHER_UNITS = w.get('units', Config.WEATHER_UNITS)
            
            if 'calendar' in data:
                c = data['calendar']
                Config.CALENDAR_UPDATE_INTERVAL = c.get('update_interval', Config.CALENDAR_UPDATE_INTERVAL)
                Config.MAX_EVENTS_DISPLAY = c.get('max_events', Config.MAX_EVENTS_DISPLAY)
                if c.get('accounts'):
                    Config.CALDAV_ACCOUNTS = c['accounts']
            
            if 'spotify' in data:
                s = data['spotify']
                Config.SPOTIFY_CLIENT_ID = s.get('client_id', Config.SPOTIFY_CLIENT_ID)
                Config.SPOTIFY_CLIENT_SECRET = s.get('client_secret', Config.SPOTIFY_CLIENT_SECRET)
                Config.SPOTIFY_REDIRECT_URI = s.get('redirect_uri', Config.SPOTIFY_REDIRECT_URI)
                Config.SPOTIFY_ACCESS_TOKEN = s.get('access_token', Config.SPOTIFY_ACCESS_TOKEN)
                Config.SPOTIFY_REFRESH_TOKEN = s.get('refresh_token', Config.SPOTIFY_REFRESH_TOKEN)
                Config.SPOTIFY_TOKEN_EXPIRES_AT = s.get('token_expires_at', Config.SPOTIFY_TOKEN_EXPIRES_AT)
                Config.SPOTIFY_USER_ID = s.get('user_id', Config.SPOTIFY_USER_ID)
                Config.SPOTIFY_CONNECTED = s.get('connected', Config.SPOTIFY_CONNECTED)
            
            if 'nest' in data:
                n = data['nest']
                Config.NEST_PROJECT_ID = n.get('project_id', Config.NEST_PROJECT_ID)
                Config.NEST_CLIENT_ID = n.get('client_id', Config.NEST_CLIENT_ID)
                Config.NEST_CLIENT_SECRET = n.get('client_secret', Config.NEST_CLIENT_SECRET)
                Config.NEST_REDIRECT_URI = n.get('redirect_uri', Config.NEST_REDIRECT_URI)
                Config.NEST_ACCESS_TOKEN = n.get('access_token', Config.NEST_ACCESS_TOKEN)
                Config.NEST_REFRESH_TOKEN = n.get('refresh_token', Config.NEST_REFRESH_TOKEN)
                Config.NEST_TOKEN_EXPIRES_AT = n.get('token_expires_at', Config.NEST_TOKEN_EXPIRES_AT)
                Config.NEST_CONNECTED = n.get('connected', Config.NEST_CONNECTED)
                Config.NEST_LAST_SYNC = n.get('last_sync', Config.NEST_LAST_SYNC)
            
            logger.info(f"Config loaded from {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")

@app.get("/notes", response_class=HTMLResponse)
async def notes_editor():
    """Serve the notes editor page"""
    note = await note_fetcher.fetch_note()
    content = note.get('content', '')
    last_modified = note.get('last_modified', 'Never')
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Clock Notes</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        
        .editor-container {{
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 40px;
            width: 100%;
            max-width: 700px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        h1 {{
            color: #fff;
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        h1::before {{
            content: "📝";
        }}
        
        .subtitle {{
            color: rgba(255, 255, 255, 0.5);
            font-size: 14px;
            margin-bottom: 30px;
        }}
        
        textarea {{
            width: 100%;
            height: 350px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 20px;
            font-family: 'Inter', monospace;
            font-size: 16px;
            line-height: 1.6;
            color: #fff;
            resize: vertical;
            outline: none;
            transition: all 0.3s ease;
        }}
        
        textarea:focus {{
            border-color: rgba(99, 179, 237, 0.5);
            box-shadow: 0 0 20px rgba(99, 179, 237, 0.2);
        }}
        
        textarea::placeholder {{
            color: rgba(255, 255, 255, 0.3);
        }}
        
        .actions {{
            display: flex;
            gap: 15px;
            margin-top: 25px;
            flex-wrap: wrap;
        }}
        
        button {{
            flex: 1;
            padding: 16px 24px;
            border: none;
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 140px;
        }}
        
        .save-btn {{
            background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
            color: white;
        }}
        
        .save-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(72, 187, 120, 0.4);
        }}
        
        .back-btn {{
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .back-btn:hover {{
            background: rgba(255, 255, 255, 0.15);
        }}
        
        .status {{
            margin-top: 20px;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            display: none;
        }}
        
        .status.success {{
            display: block;
            background: rgba(72, 187, 120, 0.2);
            color: #68d391;
            border: 1px solid rgba(72, 187, 120, 0.3);
        }}
        
        .status.error {{
            display: block;
            background: rgba(245, 101, 101, 0.2);
            color: #fc8181;
            border: 1px solid rgba(245, 101, 101, 0.3);
        }}
        
        .meta {{
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
            margin-top: 15px;
        }}
        
        @media (max-width: 500px) {{
            .editor-container {{
                padding: 25px;
            }}
            h1 {{
                font-size: 22px;
            }}
            textarea {{
                height: 280px;
            }}
            .actions {{
                flex-direction: column;
            }}
            button {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="editor-container">
        <h1>Edit Clock Notes</h1>
        <p class="subtitle">This note will display on your clock dashboard</p>
        
        <form id="noteForm">
            <textarea 
                name="content" 
                id="noteContent" 
                placeholder="Write your notes here..."
            >{content}</textarea>
            
            <div class="actions">
                <button type="submit" class="save-btn">💾 Save Note</button>
                <a href="/" style="flex: 1; text-decoration: none;">
                    <button type="button" class="back-btn" style="width: 100%;">← Back to Clock</button>
                </a>
            </div>
        </form>
        
        <div id="status" class="status"></div>
        <p class="meta">Last modified: {last_modified}</p>
    </div>
    
    <script>
        document.getElementById('noteForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const status = document.getElementById('status');
            const content = document.getElementById('noteContent').value;
            
            try {{
                const formData = new FormData();
                formData.append('content', content);
                
                const response = await fetch('/api/notes', {{
                    method: 'POST',
                    body: formData
                }});
                
                const result = await response.json();
                
                if (result.success) {{
                    status.textContent = '✓ Note saved successfully!';
                    status.className = 'status success';
                    setTimeout(() => {{ status.className = 'status'; }}, 3000);
                }} else {{
                    status.textContent = '✗ Error: ' + result.error;
                    status.className = 'status error';
                }}
            }} catch (err) {{
                status.textContent = '✗ Error saving note: ' + err.message;
                status.className = 'status error';
            }}
        }});
        
        // Auto-save with Ctrl+S / Cmd+S
        document.addEventListener('keydown', (e) => {{
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
                e.preventDefault();
                document.getElementById('noteForm').dispatchEvent(new Event('submit'));
            }}
        }});
    </script>
</body>
</html>'''
    return HTMLResponse(content=html)

@app.get("/cust", response_class=HTMLResponse)
async def customization_page():
    """Theme customization page"""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clockie - Theme Customization</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: #0a0a0f;
            min-height: 100vh;
            color: #fff;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 50px;
        }
        
        h1 {
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: rgba(255,255,255,0.5);
            font-size: 1.1rem;
        }
        
        .current-theme {
            text-align: center;
            margin-bottom: 30px;
            padding: 15px 25px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            display: inline-block;
        }
        
        .current-theme span {
            color: #667eea;
            font-weight: 600;
        }
        
        .themes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }
        
        .theme-card {
            position: relative;
            border-radius: 20px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.4s ease;
            border: 2px solid transparent;
            aspect-ratio: 16/10;
        }
        
        .theme-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        }
        
        .theme-card.active {
            border-color: #667eea;
            box-shadow: 0 0 30px rgba(102, 126, 234, 0.4);
        }
        
        .theme-preview {
            position: absolute;
            inset: 0;
            overflow: hidden;
        }
        
        .theme-info {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 20px;
            background: linear-gradient(transparent, rgba(0,0,0,0.8));
        }
        
        .theme-name {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 4px;
        }
        
        .theme-desc {
            font-size: 0.85rem;
            color: rgba(255,255,255,0.6);
        }
        
        .theme-badge {
            position: absolute;
            top: 15px;
            right: 15px;
            padding: 5px 12px;
            background: rgba(102, 126, 234, 0.9);
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            opacity: 0;
            transform: translateY(-10px);
            transition: all 0.3s ease;
        }
        
        .theme-card.active .theme-badge {
            opacity: 1;
            transform: translateY(0);
        }
        
        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 14px 28px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .back-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
        }
        
        /* ========== THEME PREVIEWS ========== */
        
        /* Flowcean (Original) */
        .preview-flowcean {
            background: #080a10;
        }
        .preview-flowcean .blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(40px);
            animation: flowceanMove 8s ease-in-out infinite;
        }
        .preview-flowcean .blob-1 {
            width: 60%; height: 60%;
            top: -10%; left: -10%;
            background: rgba(25, 35, 55, 0.8);
            animation-delay: 0s;
        }
        .preview-flowcean .blob-2 {
            width: 50%; height: 50%;
            bottom: -10%; right: -10%;
            background: rgba(35, 28, 50, 0.7);
            animation-delay: -2s;
        }
        .preview-flowcean .blob-3 {
            width: 40%; height: 40%;
            top: 30%; left: 30%;
            background: rgba(40, 32, 45, 0.6);
            animation-delay: -4s;
        }
        
        /* Aurora */
        .preview-aurora {
            background: linear-gradient(180deg, #0a0a20 0%, #1a1a3a 100%);
        }
        .preview-aurora .wave {
            position: absolute;
            width: 200%;
            height: 100%;
            background: linear-gradient(180deg, 
                transparent 0%,
                rgba(0, 255, 136, 0.15) 20%,
                rgba(0, 200, 255, 0.2) 40%,
                rgba(138, 43, 226, 0.15) 60%,
                transparent 100%);
            animation: auroraWave 6s ease-in-out infinite;
            filter: blur(20px);
        }
        .preview-aurora .wave:nth-child(2) {
            animation-delay: -2s;
            opacity: 0.7;
        }
        .preview-aurora .wave:nth-child(3) {
            animation-delay: -4s;
            opacity: 0.5;
        }
        
        /* Nebula */
        .preview-nebula {
            background: radial-gradient(ellipse at center, #1a0a2e 0%, #0a0a15 100%);
        }
        .preview-nebula .cloud {
            position: absolute;
            border-radius: 50%;
            filter: blur(30px);
            animation: nebulaFloat 10s ease-in-out infinite;
        }
        .preview-nebula .cloud-1 {
            width: 80%; height: 80%;
            top: -20%; left: -20%;
            background: radial-gradient(circle, rgba(138, 43, 226, 0.4) 0%, transparent 70%);
        }
        .preview-nebula .cloud-2 {
            width: 60%; height: 60%;
            bottom: -10%; right: -10%;
            background: radial-gradient(circle, rgba(255, 0, 128, 0.3) 0%, transparent 70%);
            animation-delay: -3s;
        }
        .preview-nebula .cloud-3 {
            width: 40%; height: 40%;
            top: 20%; right: 20%;
            background: radial-gradient(circle, rgba(0, 150, 255, 0.3) 0%, transparent 70%);
            animation-delay: -6s;
        }
        
        /* Lava */
        .preview-lava {
            background: #1a0a0a;
        }
        .preview-lava .magma {
            position: absolute;
            border-radius: 50%;
            filter: blur(35px);
            animation: lavaFlow 7s ease-in-out infinite;
        }
        .preview-lava .magma-1 {
            width: 70%; height: 70%;
            bottom: -20%; left: -10%;
            background: radial-gradient(circle, rgba(255, 100, 0, 0.6) 0%, rgba(255, 50, 0, 0.3) 50%, transparent 70%);
        }
        .preview-lava .magma-2 {
            width: 50%; height: 50%;
            bottom: 10%; right: 0%;
            background: radial-gradient(circle, rgba(255, 200, 0, 0.5) 0%, rgba(255, 100, 0, 0.2) 50%, transparent 70%);
            animation-delay: -2s;
        }
        .preview-lava .magma-3 {
            width: 30%; height: 30%;
            top: 20%; left: 20%;
            background: radial-gradient(circle, rgba(255, 50, 0, 0.4) 0%, transparent 70%);
            animation-delay: -4s;
        }
        
        /* Forest */
        .preview-forest {
            background: linear-gradient(180deg, #0a1a0a 0%, #0a150a 100%);
        }
        .preview-forest .leaf {
            position: absolute;
            border-radius: 50%;
            filter: blur(40px);
            animation: forestSway 9s ease-in-out infinite;
        }
        .preview-forest .leaf-1 {
            width: 60%; height: 60%;
            top: -10%; left: -10%;
            background: rgba(34, 139, 34, 0.4);
        }
        .preview-forest .leaf-2 {
            width: 50%; height: 50%;
            bottom: -10%; right: -10%;
            background: rgba(0, 100, 0, 0.35);
            animation-delay: -3s;
        }
        .preview-forest .leaf-3 {
            width: 40%; height: 40%;
            top: 30%; right: 10%;
            background: rgba(50, 205, 50, 0.25);
            animation-delay: -6s;
        }
        
        /* Sunset */
        .preview-sunset {
            background: linear-gradient(180deg, #1a1a2e 0%, #2d1b3d 50%, #1a0a1a 100%);
        }
        .preview-sunset .glow {
            position: absolute;
            border-radius: 50%;
            filter: blur(50px);
            animation: sunsetPulse 8s ease-in-out infinite;
        }
        .preview-sunset .glow-1 {
            width: 100%; height: 60%;
            bottom: -20%; left: 0%;
            background: radial-gradient(ellipse at bottom, rgba(255, 100, 50, 0.5) 0%, rgba(255, 50, 100, 0.3) 40%, transparent 70%);
        }
        .preview-sunset .glow-2 {
            width: 60%; height: 40%;
            bottom: 10%; left: 20%;
            background: radial-gradient(circle, rgba(255, 200, 100, 0.4) 0%, transparent 70%);
            animation-delay: -2s;
        }
        
        /* Ocean */
        .preview-ocean {
            background: linear-gradient(180deg, #001020 0%, #002040 100%);
        }
        .preview-ocean .wave {
            position: absolute;
            width: 200%;
            height: 50%;
            background: linear-gradient(180deg, transparent 0%, rgba(0, 100, 200, 0.2) 50%, transparent 100%);
            border-radius: 50%;
            animation: oceanWave 5s ease-in-out infinite;
            filter: blur(20px);
        }
        .preview-ocean .wave:nth-child(2) {
            top: 30%;
            animation-delay: -1.5s;
            opacity: 0.7;
        }
        .preview-ocean .wave:nth-child(3) {
            top: 60%;
            animation-delay: -3s;
            opacity: 0.5;
        }
        
        /* Neon */
        .preview-neon {
            background: #050510;
        }
        .preview-neon .line {
            position: absolute;
            height: 2px;
            background: linear-gradient(90deg, transparent, #ff00ff, #00ffff, transparent);
            filter: blur(3px);
            animation: neonScan 4s linear infinite;
        }
        .preview-neon .line:nth-child(1) { top: 20%; width: 80%; left: 10%; animation-delay: 0s; }
        .preview-neon .line:nth-child(2) { top: 50%; width: 60%; left: 20%; animation-delay: -1s; }
        .preview-neon .line:nth-child(3) { top: 80%; width: 70%; left: 15%; animation-delay: -2s; }
        .preview-neon .glow {
            position: absolute;
            width: 40%; height: 40%;
            border-radius: 50%;
            filter: blur(60px);
            background: rgba(255, 0, 255, 0.2);
            top: 20%; left: 30%;
            animation: neonPulse 3s ease-in-out infinite;
        }
        
        /* Minimal */
        .preview-minimal {
            background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
        }
        .preview-minimal .gradient {
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(100, 100, 100, 0.1) 0%, transparent 50%, rgba(80, 80, 80, 0.1) 100%);
            animation: minimalShift 12s ease-in-out infinite;
        }
        
        /* Candy */
        .preview-candy {
            background: #1a1020;
        }
        .preview-candy .bubble {
            position: absolute;
            border-radius: 50%;
            filter: blur(40px);
            animation: candyFloat 8s ease-in-out infinite;
        }
        .preview-candy .bubble-1 {
            width: 50%; height: 50%;
            top: -10%; left: -10%;
            background: rgba(255, 150, 200, 0.4);
        }
        .preview-candy .bubble-2 {
            width: 40%; height: 40%;
            top: 20%; right: -5%;
            background: rgba(150, 200, 255, 0.35);
            animation-delay: -2s;
        }
        .preview-candy .bubble-3 {
            width: 35%; height: 35%;
            bottom: -5%; left: 30%;
            background: rgba(200, 255, 150, 0.3);
            animation-delay: -4s;
        }
        .preview-candy .bubble-4 {
            width: 30%; height: 30%;
            bottom: 20%; right: 20%;
            background: rgba(255, 200, 100, 0.35);
            animation-delay: -6s;
        }
        
        /* Photos */
        .preview-photos {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        .preview-photos .photo-icon {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            animation: photoFloat 3s ease-in-out infinite;
        }
        .preview-photos .photo-grid-mini {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 4px;
            width: 50%;
        }
        .preview-photos .mini-photo {
            aspect-ratio: 1;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 4px;
            animation: photoFade 4s ease-in-out infinite;
        }
        .preview-photos .mini-photo:nth-child(2) { animation-delay: -1s; }
        .preview-photos .mini-photo:nth-child(3) { animation-delay: -2s; }
        .preview-photos .mini-photo:nth-child(4) { animation-delay: -3s; }
        
        @keyframes photoFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        @keyframes photoFade {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.8; }
        }
        
        /* ========== ANIMATIONS ========== */
        @keyframes flowceanMove {
            0%, 100% { transform: translate(0, 0) scale(1); }
            50% { transform: translate(10%, 10%) scale(1.1); }
        }
        @keyframes auroraWave {
            0%, 100% { transform: translateX(-25%) rotate(-5deg); }
            50% { transform: translateX(0%) rotate(5deg); }
        }
        @keyframes nebulaFloat {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.8; }
            50% { transform: translate(5%, 5%) scale(1.1); opacity: 1; }
        }
        @keyframes lavaFlow {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(5%, -5%) scale(1.05); }
            66% { transform: translate(-5%, 5%) scale(0.95); }
        }
        @keyframes forestSway {
            0%, 100% { transform: translate(0, 0) rotate(0deg); }
            50% { transform: translate(3%, 2%) rotate(2deg); }
        }
        @keyframes sunsetPulse {
            0%, 100% { transform: scale(1); opacity: 0.8; }
            50% { transform: scale(1.1); opacity: 1; }
        }
        @keyframes oceanWave {
            0%, 100% { transform: translateX(-25%) translateY(0); }
            50% { transform: translateX(0%) translateY(-10px); }
        }
        @keyframes neonScan {
            0% { transform: translateX(-100%); opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { transform: translateX(100%); opacity: 0; }
        }
        @keyframes neonPulse {
            0%, 100% { transform: scale(1); opacity: 0.3; }
            50% { transform: scale(1.2); opacity: 0.5; }
        }
        @keyframes minimalShift {
            0%, 100% { background-position: 0% 0%; }
            50% { background-position: 100% 100%; }
        }
        @keyframes candyFloat {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(5%, 5%) scale(1.05); }
            50% { transform: translate(0%, 10%) scale(1); }
            75% { transform: translate(-5%, 5%) scale(0.95); }
        }
        
        /* ========== HOLIDAY THEME PREVIEWS ========== */
        
        .holiday-card {
            border: 2px solid rgba(255,255,255,0.1);
        }
        .holiday-card:hover {
            border-color: rgba(255,215,0,0.5);
        }
        
        /* Christmas */
        .preview-christmas {
            background: linear-gradient(180deg, #0a1628 0%, #162447 50%, #1f4068 100%);
        }
        .preview-christmas .snow {
            position: absolute;
            width: 4px; height: 4px;
            background: white;
            border-radius: 50%;
            animation: snowFall 3s linear infinite;
            box-shadow: 0 0 10px rgba(255,255,255,0.8);
        }
        .preview-christmas .snow:nth-child(1) { left: 20%; animation-delay: 0s; }
        .preview-christmas .snow:nth-child(2) { left: 50%; animation-delay: -1s; }
        .preview-christmas .snow:nth-child(3) { left: 80%; animation-delay: -2s; }
        .preview-christmas .glow-red {
            position: absolute;
            width: 60%; height: 60%;
            bottom: -20%; left: -10%;
            background: radial-gradient(circle, rgba(220, 20, 60, 0.4) 0%, transparent 70%);
            filter: blur(20px);
        }
        .preview-christmas .glow-green {
            position: absolute;
            width: 50%; height: 50%;
            top: -10%; right: -10%;
            background: radial-gradient(circle, rgba(0, 128, 0, 0.35) 0%, transparent 70%);
            filter: blur(20px);
        }
        
        /* Christmas Eve */
        .preview-christmas-eve {
            background: linear-gradient(180deg, #0d1b2a 0%, #1b2838 50%, #2c3e50 100%);
        }
        .preview-christmas-eve .star {
            position: absolute;
            width: 6px; height: 6px;
            background: gold;
            border-radius: 50%;
            animation: starTwinkle 2s ease-in-out infinite;
            box-shadow: 0 0 15px rgba(255,215,0,0.8);
        }
        .preview-christmas-eve .star:nth-child(1) { top: 20%; left: 30%; }
        .preview-christmas-eve .star:nth-child(2) { top: 40%; left: 70%; animation-delay: -0.7s; }
        .preview-christmas-eve .star:nth-child(3) { top: 60%; left: 50%; animation-delay: -1.4s; }
        .preview-christmas-eve .glow-gold {
            position: absolute;
            width: 80%; height: 60%;
            bottom: -20%; left: 10%;
            background: radial-gradient(ellipse, rgba(255, 215, 0, 0.25) 0%, transparent 70%);
            filter: blur(25px);
        }
        
        /* New Year */
        .preview-newyear {
            background: linear-gradient(180deg, #0a0a1a 0%, #1a1a2e 50%, #16213e 100%);
        }
        .preview-newyear .confetti-p {
            position: absolute;
            width: 8px; height: 8px;
            background: gold;
            animation: confettiPop 2s ease-out infinite;
        }
        .preview-newyear .confetti-p:nth-child(1) { left: 30%; background: #ff6b6b; }
        .preview-newyear .confetti-p:nth-child(2) { left: 50%; background: #ffd93d; animation-delay: -0.5s; }
        .preview-newyear .confetti-p:nth-child(3) { left: 70%; background: #6bcb77; animation-delay: -1s; }
        .preview-newyear .gold-burst {
            position: absolute;
            width: 70%; height: 70%;
            top: 15%; left: 15%;
            background: radial-gradient(circle, rgba(255, 215, 0, 0.3) 0%, transparent 60%);
            filter: blur(20px);
            animation: burstPulse 2s ease-in-out infinite;
        }
        
        /* New Year's Eve */
        .preview-newyears-eve {
            background: linear-gradient(180deg, #0f0f23 0%, #1a1a3a 50%, #2d1b4e 100%);
        }
        .preview-newyears-eve .sparkle-p {
            position: absolute;
            width: 4px; height: 4px;
            background: white;
            border-radius: 50%;
            animation: sparklePop 1.5s ease-in-out infinite;
            box-shadow: 0 0 10px gold;
        }
        .preview-newyears-eve .sparkle-p:nth-child(1) { top: 30%; left: 25%; }
        .preview-newyears-eve .sparkle-p:nth-child(2) { top: 50%; left: 60%; animation-delay: -0.5s; }
        .preview-newyears-eve .sparkle-p:nth-child(3) { top: 40%; left: 80%; animation-delay: -1s; }
        .preview-newyears-eve .champagne-glow {
            position: absolute;
            width: 60%; height: 60%;
            bottom: 0; left: 20%;
            background: radial-gradient(circle, rgba(218, 165, 32, 0.35) 0%, transparent 70%);
            filter: blur(25px);
        }
        
        /* Valentine's */
        .preview-valentine {
            background: linear-gradient(180deg, #1a0a14 0%, #2d1520 50%, #3d1a2a 100%);
        }
        .preview-valentine .heart-p {
            position: absolute;
            font-size: 20px;
            animation: heartRise 3s ease-in-out infinite;
        }
        .preview-valentine .heart-p::before { content: '❤'; }
        .preview-valentine .heart-p:nth-child(1) { left: 25%; animation-delay: 0s; }
        .preview-valentine .heart-p:nth-child(2) { left: 50%; animation-delay: -1s; }
        .preview-valentine .heart-p:nth-child(3) { left: 75%; animation-delay: -2s; }
        .preview-valentine .pink-glow {
            position: absolute;
            width: 80%; height: 80%;
            top: 10%; left: 10%;
            background: radial-gradient(circle, rgba(255, 20, 147, 0.3) 0%, transparent 70%);
            filter: blur(30px);
        }
        
        /* St Patrick's */
        .preview-stpatricks {
            background: linear-gradient(180deg, #0a1a0f 0%, #0f2a18 50%, #1a3a25 100%);
        }
        .preview-stpatricks .clover-p {
            position: absolute;
            font-size: 18px;
            animation: cloverDance 4s ease-in-out infinite;
        }
        .preview-stpatricks .clover-p::before { content: '☘️'; }
        .preview-stpatricks .clover-p:nth-child(1) { top: 20%; left: 30%; }
        .preview-stpatricks .clover-p:nth-child(2) { top: 50%; left: 60%; animation-delay: -1.3s; }
        .preview-stpatricks .clover-p:nth-child(3) { top: 70%; left: 40%; animation-delay: -2.6s; }
        .preview-stpatricks .green-glow {
            position: absolute;
            width: 70%; height: 70%;
            bottom: -10%; left: 15%;
            background: radial-gradient(circle, rgba(50, 205, 50, 0.35) 0%, transparent 70%);
            filter: blur(25px);
        }
        
        /* Easter */
        .preview-easter {
            background: linear-gradient(180deg, #1a1520 0%, #252035 50%, #2a2540 100%);
        }
        .preview-easter .egg {
            position: absolute;
            width: 15px; height: 20px;
            background: linear-gradient(135deg, #ffb6c1, #98fb98, #87ceeb);
            border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
            animation: eggBounce 3s ease-in-out infinite;
        }
        .preview-easter .egg:nth-child(1) { top: 40%; left: 30%; }
        .preview-easter .egg:nth-child(2) { top: 50%; left: 60%; animation-delay: -1s; background: linear-gradient(135deg, #dda0dd, #ffd700, #ffb6c1); }
        .preview-easter .bunny-glow {
            position: absolute;
            width: 50%; height: 50%;
            top: 10%; right: 10%;
            background: radial-gradient(circle, rgba(255, 182, 193, 0.3) 0%, transparent 70%);
            filter: blur(20px);
        }
        .preview-easter .spring-glow {
            position: absolute;
            width: 60%; height: 50%;
            bottom: -10%; left: 20%;
            background: radial-gradient(circle, rgba(152, 251, 152, 0.3) 0%, transparent 70%);
            filter: blur(20px);
        }
        
        /* 4th of July */
        .preview-july4th {
            background: linear-gradient(180deg, #0a0a1f 0%, #0f1535 50%, #1a2050 100%);
        }
        .preview-july4th .firework-p {
            position: absolute;
            width: 8px; height: 8px;
            border-radius: 50%;
            animation: fireworkExplode 2s ease-out infinite;
        }
        .preview-july4th .firework-p:nth-child(1) { top: 30%; left: 25%; background: #ff0000; box-shadow: 0 0 20px #ff0000; }
        .preview-july4th .firework-p:nth-child(2) { top: 40%; left: 50%; background: #ffffff; box-shadow: 0 0 20px #ffffff; animation-delay: -0.7s; }
        .preview-july4th .firework-p:nth-child(3) { top: 35%; left: 75%; background: #0000ff; box-shadow: 0 0 20px #0000ff; animation-delay: -1.4s; }
        .preview-july4th .usa-glow {
            position: absolute;
            width: 100%; height: 60%;
            bottom: -10%; left: 0;
            background: linear-gradient(90deg, rgba(255,0,0,0.2), rgba(255,255,255,0.2), rgba(0,0,255,0.2));
            filter: blur(30px);
        }
        
        /* Halloween */
        .preview-halloween {
            background: linear-gradient(180deg, #0a0508 0%, #1a0a15 50%, #2d0f1f 100%);
        }
        .preview-halloween .pumpkin {
            position: absolute;
            top: 50%; left: 30%;
            font-size: 30px;
            animation: pumpkinGlow 2s ease-in-out infinite;
        }
        .preview-halloween .pumpkin::before { content: '🎃'; }
        .preview-halloween .ghost {
            position: absolute;
            top: 30%; right: 25%;
            font-size: 25px;
            animation: ghostFloat 3s ease-in-out infinite;
        }
        .preview-halloween .ghost::before { content: '👻'; }
        .preview-halloween .spooky-glow {
            position: absolute;
            width: 80%; height: 60%;
            bottom: 0; left: 10%;
            background: radial-gradient(ellipse, rgba(255, 140, 0, 0.3) 0%, rgba(138, 43, 226, 0.2) 50%, transparent 70%);
            filter: blur(25px);
        }
        
        /* Thanksgiving */
        .preview-thanksgiving {
            background: linear-gradient(180deg, #1a0f08 0%, #2d1a10 50%, #3d2518 100%);
        }
        .preview-thanksgiving .leaf-p {
            position: absolute;
            font-size: 20px;
            animation: leafFall 4s ease-in-out infinite;
        }
        .preview-thanksgiving .leaf-p:nth-child(1)::before { content: '🍂'; }
        .preview-thanksgiving .leaf-p:nth-child(2)::before { content: '🍁'; }
        .preview-thanksgiving .leaf-p:nth-child(3)::before { content: '🍂'; }
        .preview-thanksgiving .leaf-p:nth-child(1) { left: 25%; }
        .preview-thanksgiving .leaf-p:nth-child(2) { left: 55%; animation-delay: -1.3s; }
        .preview-thanksgiving .leaf-p:nth-child(3) { left: 80%; animation-delay: -2.6s; }
        .preview-thanksgiving .autumn-glow {
            position: absolute;
            width: 70%; height: 70%;
            bottom: -20%; left: 15%;
            background: radial-gradient(circle, rgba(210, 105, 30, 0.4) 0%, transparent 70%);
            filter: blur(25px);
        }
        
        /* Memorial Day */
        .preview-memorial {
            background: linear-gradient(180deg, #0a0a18 0%, #0f1525 50%, #1a2035 100%);
        }
        .preview-memorial .flag-stripe {
            position: absolute;
            height: 10%;
            left: 10%; right: 10%;
            animation: flagWave 3s ease-in-out infinite;
        }
        .preview-memorial .flag-stripe:nth-child(1) { top: 30%; background: rgba(178, 34, 52, 0.6); }
        .preview-memorial .flag-stripe:nth-child(2) { top: 50%; background: rgba(255, 255, 255, 0.4); animation-delay: -0.5s; }
        .preview-memorial .patriot-glow {
            position: absolute;
            width: 60%; height: 60%;
            bottom: -10%; left: 20%;
            background: radial-gradient(circle, rgba(0, 40, 104, 0.4) 0%, transparent 70%);
            filter: blur(25px);
        }
        
        /* Labor Day */
        .preview-labor {
            background: linear-gradient(180deg, #0f0f18 0%, #1a1a2a 50%, #252540 100%);
        }
        .preview-labor .worker-glow {
            position: absolute;
            width: 60%; height: 60%;
            top: 20%; left: 20%;
            background: radial-gradient(circle, rgba(65, 105, 225, 0.35) 0%, transparent 70%);
            filter: blur(25px);
        }
        .preview-labor .star-p {
            position: absolute;
            font-size: 18px;
            animation: starSpin 4s linear infinite;
        }
        .preview-labor .star-p::before { content: '⭐'; }
        .preview-labor .star-p:nth-child(2) { top: 25%; left: 60%; }
        .preview-labor .star-p:nth-child(3) { top: 60%; left: 30%; animation-delay: -2s; }
        
        /* Holiday animations */
        @keyframes snowFall {
            0% { top: -10%; opacity: 0; }
            10% { opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
        @keyframes starTwinkle {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.8); }
        }
        @keyframes confettiPop {
            0% { top: 80%; opacity: 0; transform: rotate(0deg); }
            50% { opacity: 1; }
            100% { top: 20%; opacity: 0; transform: rotate(360deg); }
        }
        @keyframes burstPulse {
            0%, 100% { transform: scale(1); opacity: 0.3; }
            50% { transform: scale(1.2); opacity: 0.5; }
        }
        @keyframes sparklePop {
            0%, 100% { transform: scale(0.5); opacity: 0.3; }
            50% { transform: scale(1.2); opacity: 1; }
        }
        @keyframes heartRise {
            0% { top: 100%; opacity: 0; }
            50% { opacity: 1; }
            100% { top: -10%; opacity: 0; }
        }
        @keyframes cloverDance {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-10px) rotate(10deg); }
        }
        @keyframes eggBounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-8px); }
        }
        @keyframes fireworkExplode {
            0% { transform: scale(0.5); opacity: 0; }
            50% { transform: scale(1.5); opacity: 1; }
            100% { transform: scale(2); opacity: 0; }
        }
        @keyframes pumpkinGlow {
            0%, 100% { filter: brightness(1); }
            50% { filter: brightness(1.3); }
        }
        @keyframes ghostFloat {
            0%, 100% { transform: translateY(0) translateX(0); }
            50% { transform: translateY(-10px) translateX(5px); }
        }
        @keyframes leafFall {
            0% { top: -10%; opacity: 0; transform: rotate(0deg) translateX(0); }
            50% { opacity: 1; }
            100% { top: 100%; opacity: 0; transform: rotate(360deg) translateX(30px); }
        }
        @keyframes flagWave {
            0%, 100% { transform: skewX(0deg); }
            50% { transform: skewX(3deg); }
        }
        @keyframes starSpin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @media (max-width: 600px) {
            body { padding: 20px 15px; }
            .themes-grid { gap: 15px; }
            .theme-card { aspect-ratio: 16/9; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎨 Theme Customization</h1>
            <p class="subtitle">Choose your perfect ambient background</p>
        </header>
        
        <div style="text-align: center;">
            <div class="current-theme">
                Current Theme: <span id="currentThemeName">Flowcean</span>
            </div>
        </div>
        
        <div class="themes-grid" id="themesGrid">
            <!-- Flowcean -->
            <div class="theme-card" data-theme="flowcean">
                <div class="theme-preview preview-flowcean">
                    <div class="blob blob-1"></div>
                    <div class="blob blob-2"></div>
                    <div class="blob blob-3"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Flowcean</div>
                    <div class="theme-desc">Organic flowing shapes</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Aurora -->
            <div class="theme-card" data-theme="aurora">
                <div class="theme-preview preview-aurora">
                    <div class="wave"></div>
                    <div class="wave"></div>
                    <div class="wave"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Aurora</div>
                    <div class="theme-desc">Northern lights waves</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Nebula -->
            <div class="theme-card" data-theme="nebula">
                <div class="theme-preview preview-nebula">
                    <div class="cloud cloud-1"></div>
                    <div class="cloud cloud-2"></div>
                    <div class="cloud cloud-3"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Nebula</div>
                    <div class="theme-desc">Cosmic cloud swirls</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Lava -->
            <div class="theme-card" data-theme="lava">
                <div class="theme-preview preview-lava">
                    <div class="magma magma-1"></div>
                    <div class="magma magma-2"></div>
                    <div class="magma magma-3"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Lava</div>
                    <div class="theme-desc">Molten fire flows</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Forest -->
            <div class="theme-card" data-theme="forest">
                <div class="theme-preview preview-forest">
                    <div class="leaf leaf-1"></div>
                    <div class="leaf leaf-2"></div>
                    <div class="leaf leaf-3"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Forest</div>
                    <div class="theme-desc">Peaceful nature greens</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Sunset -->
            <div class="theme-card" data-theme="sunset">
                <div class="theme-preview preview-sunset">
                    <div class="glow glow-1"></div>
                    <div class="glow glow-2"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Sunset</div>
                    <div class="theme-desc">Warm golden hour glow</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Ocean -->
            <div class="theme-card" data-theme="ocean">
                <div class="theme-preview preview-ocean">
                    <div class="wave"></div>
                    <div class="wave"></div>
                    <div class="wave"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Ocean</div>
                    <div class="theme-desc">Deep sea waves</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Neon -->
            <div class="theme-card" data-theme="neon">
                <div class="theme-preview preview-neon">
                    <div class="line"></div>
                    <div class="line"></div>
                    <div class="line"></div>
                    <div class="glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Neon</div>
                    <div class="theme-desc">Cyberpunk glow lines</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Minimal -->
            <div class="theme-card" data-theme="minimal">
                <div class="theme-preview preview-minimal">
                    <div class="gradient"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Minimal</div>
                    <div class="theme-desc">Clean subtle gradients</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Candy -->
            <div class="theme-card" data-theme="candy">
                <div class="theme-preview preview-candy">
                    <div class="bubble bubble-1"></div>
                    <div class="bubble bubble-2"></div>
                    <div class="bubble bubble-3"></div>
                    <div class="bubble bubble-4"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Candy</div>
                    <div class="theme-desc">Playful pastel bubbles</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
            
            <!-- Photos -->
            <div class="theme-card" data-theme="photos">
                <div class="theme-preview preview-photos">
                    <div class="photo-icon">🖼️</div>
                    <div class="photo-grid-mini">
                        <div class="mini-photo"></div>
                        <div class="mini-photo"></div>
                        <div class="mini-photo"></div>
                        <div class="mini-photo"></div>
                    </div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">Photos</div>
                    <div class="theme-desc">Your photo slideshow</div>
                </div>
                <div class="theme-badge">Active</div>
            </div>
        </div>
        
        <h2 style="text-align: center; margin: 50px 0 30px; color: rgba(255,255,255,0.7); font-size: 1.5rem;">
            🎉 Holiday Themes <span style="font-size: 0.85rem; opacity: 0.6;">(Auto-activate on special days)</span>
        </h2>
        
        <div class="themes-grid" id="holidayGrid">
            <!-- Christmas -->
            <div class="theme-card holiday-card" data-holiday="christmas">
                <div class="theme-preview preview-christmas">
                    <div class="snow"></div>
                    <div class="snow"></div>
                    <div class="snow"></div>
                    <div class="glow-red"></div>
                    <div class="glow-green"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🎄 Christmas</div>
                    <div class="theme-desc">Dec 25 • Winter wonderland</div>
                </div>
            </div>
            
            <!-- Christmas Eve -->
            <div class="theme-card holiday-card" data-holiday="christmas-eve">
                <div class="theme-preview preview-christmas-eve">
                    <div class="star"></div>
                    <div class="star"></div>
                    <div class="star"></div>
                    <div class="glow-gold"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">✨ Christmas Eve</div>
                    <div class="theme-desc">Dec 24 • Magical anticipation</div>
                </div>
            </div>
            
            <!-- New Year's Day -->
            <div class="theme-card holiday-card" data-holiday="newyear">
                <div class="theme-preview preview-newyear">
                    <div class="confetti-p"></div>
                    <div class="confetti-p"></div>
                    <div class="confetti-p"></div>
                    <div class="gold-burst"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🎉 New Year's Day</div>
                    <div class="theme-desc">Jan 1 • Celebration & joy</div>
                </div>
            </div>
            
            <!-- New Year's Eve -->
            <div class="theme-card holiday-card" data-holiday="newyears-eve">
                <div class="theme-preview preview-newyears-eve">
                    <div class="sparkle-p"></div>
                    <div class="sparkle-p"></div>
                    <div class="sparkle-p"></div>
                    <div class="champagne-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🥂 New Year's Eve</div>
                    <div class="theme-desc">Dec 31 • Glamour night</div>
                </div>
            </div>
            
            <!-- Valentine's Day -->
            <div class="theme-card holiday-card" data-holiday="valentine">
                <div class="theme-preview preview-valentine">
                    <div class="heart-p"></div>
                    <div class="heart-p"></div>
                    <div class="heart-p"></div>
                    <div class="pink-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">💕 Valentine's Day</div>
                    <div class="theme-desc">Feb 14 • Romance & love</div>
                </div>
            </div>
            
            <!-- St. Patrick's Day -->
            <div class="theme-card holiday-card" data-holiday="stpatricks">
                <div class="theme-preview preview-stpatricks">
                    <div class="clover-p"></div>
                    <div class="clover-p"></div>
                    <div class="clover-p"></div>
                    <div class="green-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">☘️ St. Patrick's Day</div>
                    <div class="theme-desc">Mar 17 • Irish luck</div>
                </div>
            </div>
            
            <!-- Easter -->
            <div class="theme-card holiday-card" data-holiday="easter">
                <div class="theme-preview preview-easter">
                    <div class="egg"></div>
                    <div class="egg"></div>
                    <div class="bunny-glow"></div>
                    <div class="spring-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🐰 Easter</div>
                    <div class="theme-desc">Varies • Spring renewal</div>
                </div>
            </div>
            
            <!-- 4th of July -->
            <div class="theme-card holiday-card" data-holiday="july4th">
                <div class="theme-preview preview-july4th">
                    <div class="firework-p"></div>
                    <div class="firework-p"></div>
                    <div class="firework-p"></div>
                    <div class="usa-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🇺🇸 4th of July</div>
                    <div class="theme-desc">Jul 4 • Patriotic celebration</div>
                </div>
            </div>
            
            <!-- Halloween -->
            <div class="theme-card holiday-card" data-holiday="halloween">
                <div class="theme-preview preview-halloween">
                    <div class="pumpkin"></div>
                    <div class="ghost"></div>
                    <div class="spooky-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🎃 Halloween</div>
                    <div class="theme-desc">Oct 31 • Spooky vibes</div>
                </div>
            </div>
            
            <!-- Thanksgiving -->
            <div class="theme-card holiday-card" data-holiday="thanksgiving">
                <div class="theme-preview preview-thanksgiving">
                    <div class="leaf-p"></div>
                    <div class="leaf-p"></div>
                    <div class="leaf-p"></div>
                    <div class="autumn-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🦃 Thanksgiving</div>
                    <div class="theme-desc">4th Thu Nov • Gratitude</div>
                </div>
            </div>
            
            <!-- Memorial Day -->
            <div class="theme-card holiday-card" data-holiday="memorial">
                <div class="theme-preview preview-memorial">
                    <div class="flag-stripe"></div>
                    <div class="flag-stripe"></div>
                    <div class="patriot-glow"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">🎖️ Memorial Day</div>
                    <div class="theme-desc">Last Mon May • Honor</div>
                </div>
            </div>
            
            <!-- Labor Day -->
            <div class="theme-card holiday-card" data-holiday="labor">
                <div class="theme-preview preview-labor">
                    <div class="worker-glow"></div>
                    <div class="star-p"></div>
                    <div class="star-p"></div>
                </div>
                <div class="theme-info">
                    <div class="theme-name">💪 Labor Day</div>
                    <div class="theme-desc">1st Mon Sep • Workers</div>
                </div>
            </div>
        </div>
        
        <p style="text-align: center; color: rgba(255,255,255,0.4); margin: 20px 0 40px; font-size: 0.9rem;">
            Click any holiday theme to preview it on the clock
        </p>
        
        <div class="footer">
            <a href="/" class="back-btn">← Back to Clock</a>
        </div>
    </div>
    
    <script>
        const themeNames = {
            flowcean: 'Flowcean',
            aurora: 'Aurora',
            nebula: 'Nebula',
            lava: 'Lava',
            forest: 'Forest',
            sunset: 'Sunset',
            ocean: 'Ocean',
            neon: 'Neon',
            minimal: 'Minimal',
            candy: 'Candy',
            photos: 'Photos'
        };
        
        function getCurrentBgTheme() {
            return localStorage.getItem('clockie-bg-theme') || 'flowcean';
        }
        
        function setBgTheme(theme) {
            localStorage.setItem('clockie-bg-theme', theme);
            updateUI();
        }
        
        function updateUI() {
            const current = getCurrentBgTheme();
            document.getElementById('currentThemeName').textContent = themeNames[current] || 'Flowcean';
            
            document.querySelectorAll('.theme-card').forEach(card => {
                card.classList.toggle('active', card.dataset.theme === current);
            });
        }
        
        // Initialize
        updateUI();
        
        // Theme selection
        document.querySelectorAll('.theme-card:not(.holiday-card)').forEach(card => {
            card.addEventListener('click', () => {
                setBgTheme(card.dataset.theme);
            });
        });
        
        // Holiday theme preview - opens clock with holiday applied
        document.querySelectorAll('.holiday-card').forEach(card => {
            card.addEventListener('click', () => {
                const holiday = card.dataset.holiday;
                // Store holiday preview request
                localStorage.setItem('clockie-holiday-preview', holiday);
                // Navigate to clock
                window.location.href = '/?preview_holiday=' + holiday;
            });
        });
    </script>
</body>
</html>'''
    return HTMLResponse(content=html)

@app.get("/api/time")
async def get_time():
    """Get current server time"""
    now = datetime.now()
    return {
        'time': now.strftime("%I:%M:%S %p"),
        'date': now.strftime("%A, %B %d, %Y"),
        'timestamp': now.isoformat()
    }

# ============================================================================
# PHOTO MANAGEMENT API
# ============================================================================

@app.get("/upload")
async def upload_page():
    """Serve the photo upload/management page"""
    return FileResponse("frontend/upload.html")

@app.get("/api/photos")
async def list_photos():
    """List all photos in the photos directory"""
    photos = []
    for f in PHOTOS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            stat = f.stat()
            photos.append({
                'filename': f.name,
                'url': f'/photos/{f.name}',
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    # Sort by modified date, newest first
    photos.sort(key=lambda x: x['modified'], reverse=True)
    return {'photos': photos, 'count': len(photos)}

@app.post("/api/photos/upload")
async def upload_photo(file: UploadFile = File(...)):
    """Upload a new photo"""
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(400, f"File too large. Max size: {MAX_PHOTO_SIZE // (1024*1024)}MB")
    
    try:
        # Open image with PIL to validate and optionally resize
        img = Image.open(io.BytesIO(content))
        
        # Auto-fix EXIF orientation (rotates image based on phone orientation data)
        img = ImageOps.exif_transpose(img)
        
        # Convert RGBA to RGB for JPEG
        if img.mode == 'RGBA' and ext in ['.jpg', '.jpeg']:
            img = img.convert('RGB')
        
        # Resize if too large (preserve aspect ratio)
        if max(img.size) > PHOTO_MAX_DIMENSION:
            img.thumbnail((PHOTO_MAX_DIMENSION, PHOTO_MAX_DIMENSION), Image.Resampling.LANCZOS)
        
        # Generate unique filename
        unique_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).stem}{ext}"
        save_path = PHOTOS_DIR / unique_name
        
        # Save optimized image
        if ext in ['.jpg', '.jpeg']:
            img.save(save_path, 'JPEG', quality=85, optimize=True)
        elif ext == '.png':
            img.save(save_path, 'PNG', optimize=True)
        elif ext == '.webp':
            img.save(save_path, 'WEBP', quality=85)
        else:
            img.save(save_path)
        
        logger.info(f"Photo uploaded: {unique_name}")
        
        return {
            'success': True,
            'filename': unique_name,
            'url': f'/photos/{unique_name}',
            'size': save_path.stat().st_size
        }
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(400, f"Error processing image: {str(e)}")

@app.delete("/api/photos/{filename}")
async def delete_photo(filename: str):
    """Delete a photo"""
    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    photo_path = PHOTOS_DIR / safe_name
    
    if not photo_path.exists():
        raise HTTPException(404, "Photo not found")
    
    if not photo_path.is_file():
        raise HTTPException(400, "Invalid file")
    
    try:
        photo_path.unlink()
        logger.info(f"Photo deleted: {safe_name}")
        return {'success': True, 'deleted': safe_name}
    except Exception as e:
        logger.error(f"Error deleting photo: {e}")
        raise HTTPException(500, f"Error deleting photo: {str(e)}")

@app.get("/api/photos/random")
async def random_photo():
    """Get a random photo for slideshow"""
    import random
    photos = [f for f in PHOTOS_DIR.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS]
    if not photos:
        return {'photo': None}
    photo = random.choice(photos)
    return {
        'photo': {
            'filename': photo.name,
            'url': f'/photos/{photo.name}'
        }
    }

@app.post("/api/photos/{filename}/rotate")
async def rotate_photo(filename: str, direction: str = "cw"):
    """Rotate a photo 90 degrees clockwise (cw) or counter-clockwise (ccw)"""
    # Sanitize filename to prevent path traversal
    safe_name = Path(filename).name
    photo_path = PHOTOS_DIR / safe_name
    
    if not photo_path.exists():
        raise HTTPException(404, "Photo not found")
    
    if not photo_path.is_file():
        raise HTTPException(400, "Invalid file")
    
    ext = photo_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Invalid file type")
    
    try:
        # Open and rotate
        img = Image.open(photo_path)
        
        # Rotate based on direction
        if direction == "ccw":
            img = img.rotate(90, expand=True)
        else:  # Default clockwise
            img = img.rotate(-90, expand=True)
        
        # Save back
        if ext in ['.jpg', '.jpeg']:
            img.save(photo_path, 'JPEG', quality=90, optimize=True)
        elif ext == '.png':
            img.save(photo_path, 'PNG', optimize=True)
        elif ext == '.webp':
            img.save(photo_path, 'WEBP', quality=90)
        else:
            img.save(photo_path)
        
        logger.info(f"Photo rotated {direction}: {safe_name}")
        return {
            'success': True,
            'filename': safe_name,
            'url': f'/photos/{safe_name}?t={datetime.now().timestamp()}'  # Cache bust
        }
        
    except Exception as e:
        logger.error(f"Error rotating photo: {e}")
        raise HTTPException(500, f"Error rotating photo: {str(e)}")

# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    logger.info("WebSocket client connected")

    try:
        # Send initial data
        await websocket.send_json({
            'type': 'weather',
            'data': await weather_fetcher.fetch_weather()
        })
        await websocket.send_json({
            'type': 'calendar',
            'data': await calendar_fetcher.fetch_events()
        })
        await websocket.send_json({
            'type': 'notes',
            'data': await note_fetcher.fetch_note()
        })
        
        # Send initial Jarvis briefing
        initial_weather = await weather_fetcher.fetch_weather()
        initial_events = await calendar_fetcher.fetch_events()
        initial_today = [e for e in initial_events if e.get('is_today', False)]
        initial_upcoming = [e for e in initial_events if e.get('is_upcoming', False)]
        
        jarvis_briefing = await jarvis_agent.generate_briefing(
            weather=initial_weather,
            today_events=initial_today,
            upcoming_events=initial_upcoming
        )
        await websocket.send_json({
            'type': 'jarvis',
            'data': jarvis_briefing
        })

        # Keep connection alive and send updates
        while True:
            # Wait for next update cycle
            await asyncio.sleep(60)  # Check every minute

            # Send time update
            now = datetime.now()
            await websocket.send_json({
                'type': 'time',
                'data': {
                    'time': now.strftime("%I:%M:%S %p"),
                    'date': now.strftime("%A, %B %d, %Y")
                }
            })

            # Send weather update (every 10 minutes)
            weather_data = None
            if now.minute % 10 == 0:
                weather_data = await weather_fetcher.fetch_weather()
                await websocket.send_json({
                    'type': 'weather',
                    'data': weather_data
                })

            # Send calendar update (every 5 minutes)
            events_data = None
            today_events = []
            upcoming_events = []
            if now.minute % 5 == 0:
                events_data = await calendar_fetcher.fetch_events()
                today_events = [e for e in events_data if e.get('is_today', False)]
                upcoming_events = [e for e in events_data if e.get('is_upcoming', False)]

                await websocket.send_json({
                    'type': 'calendar',
                    'data': {
                        'today': today_events,
                        'upcoming': upcoming_events
                    }
                })

            # Send notes update (every minute)
            await websocket.send_json({
                'type': 'notes',
                'data': await note_fetcher.fetch_note()
            })
            
            # Send Jarvis update (checks internally if needed - every 30 min or on significant change)
            # Get fresh data if we don't have it from above
            if weather_data is None:
                weather_data = await weather_fetcher.fetch_weather()
            if events_data is None:
                events_data = await calendar_fetcher.fetch_events()
                today_events = [e for e in events_data if e.get('is_today', False)]
                upcoming_events = [e for e in events_data if e.get('is_upcoming', False)]
            
            jarvis_briefing = await jarvis_agent.generate_briefing(
                weather=weather_data,
                today_events=today_events,
                upcoming_events=upcoming_events
            )
            
            # Only send if it's a new message (not cached from same minute)
            if jarvis_briefing.get('source') != 'cached' or now.minute % 30 == 0:
                await websocket.send_json({
                    'type': 'jarvis',
                    'data': jarvis_briefing
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")

# ============================================================================
# HOME HUB - ZIGBEE/SMART HOME INTEGRATION
# ============================================================================

class HomeHubManager:
    """
    Manages Zigbee devices via Zigbee2MQTT over MQTT.
    Provides device discovery, control, and automation capabilities.
    """
    
    def __init__(self):
        self.mqtt_client = None
        self.connected = False
        self.devices = {}
        self.device_states = {}
        self.permit_join_active = False
        self.settings = {
            'mqtt_host': 'localhost',
            'mqtt_port': 1883,
            'mqtt_username': '',
            'mqtt_password': '',
            'z2m_topic': 'zigbee2mqtt',
            'auto_permit': False,
            'log_events': True,
            'temp_logging_enabled': True,
            'temp_logging_interval': 1  # minutes (1-5)
        }
        self.event_log = []
        self.automations = []
        self.scenes = []
        self._temp_log_task = None
        self._init_temp_db()
        self._load_settings()
        
    def _init_temp_db(self):
        """Initialize SQLite database for temperature logging"""
        import sqlite3
        self.temp_db_path = Path("/home/admin/wallclock/temp_history.db")
        try:
            conn = sqlite3.connect(str(self.temp_db_path))
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    device_id TEXT NOT NULL,
                    friendly_name TEXT,
                    temperature REAL,
                    humidity REAL,
                    pressure REAL,
                    battery REAL,
                    linkquality INTEGER
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_temp_device_time 
                ON temp_readings(device_id, timestamp)
            ''')
            conn.commit()
            conn.close()
            logger.info("HomeHub: Temperature database initialized")
        except Exception as e:
            logger.error(f"HomeHub: Failed to init temp database: {e}")
    
    def _log_temperature_readings(self):
        """Log current temperature readings from all sensors"""
        import sqlite3
        if not self.settings.get('temp_logging_enabled', True):
            return
        
        try:
            conn = sqlite3.connect(str(self.temp_db_path))
            cursor = conn.cursor()
            
            logged_count = 0
            for device_id, device in self.devices.items():
                if device.get('type') != 'sensor':
                    continue
                
                # Device states are keyed by friendly_name
                friendly_name = device.get('friendly_name', device_id)
                state = self.device_states.get(friendly_name, {})
                if not state:
                    continue
                
                # Only log if we have temperature data
                if 'temperature' not in state:
                    continue
                
                cursor.execute('''
                    INSERT INTO temp_readings 
                    (device_id, friendly_name, temperature, humidity, pressure, battery, linkquality)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device_id,
                    device.get('friendly_name', device_id),
                    state.get('temperature'),
                    state.get('humidity'),
                    state.get('pressure'),
                    state.get('battery'),
                    state.get('linkquality')
                ))
                logged_count += 1
            
            conn.commit()
            conn.close()
            
            if logged_count > 0:
                logger.debug(f"HomeHub: Logged {logged_count} temperature readings")
                
        except Exception as e:
            logger.error(f"HomeHub: Failed to log temperatures: {e}")
    
    def get_temp_history(self, device_id: str = None, hours: int = 24) -> list:
        """Get temperature history for a device or all devices"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.temp_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if device_id:
                cursor.execute('''
                    SELECT * FROM temp_readings 
                    WHERE device_id = ? 
                    AND timestamp > datetime('now', ?)
                    ORDER BY timestamp ASC
                ''', (device_id, f'-{hours} hours'))
            else:
                cursor.execute('''
                    SELECT * FROM temp_readings 
                    WHERE timestamp > datetime('now', ?)
                    ORDER BY timestamp ASC
                ''', (f'-{hours} hours',))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"HomeHub: Failed to get temp history: {e}")
            return []
    
    def get_temp_stats(self, device_id: str, hours: int = 24) -> dict:
        """Get temperature statistics for a device"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.temp_db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    MIN(temperature) as min_temp,
                    MAX(temperature) as max_temp,
                    AVG(temperature) as avg_temp,
                    MIN(humidity) as min_humidity,
                    MAX(humidity) as max_humidity,
                    AVG(humidity) as avg_humidity,
                    COUNT(*) as readings
                FROM temp_readings 
                WHERE device_id = ? 
                AND timestamp > datetime('now', ?)
            ''', (device_id, f'-{hours} hours'))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'min_temp': row[0],
                    'max_temp': row[1],
                    'avg_temp': row[2],
                    'min_humidity': row[3],
                    'max_humidity': row[4],
                    'avg_humidity': row[5],
                    'readings': row[6]
                }
            return {}
            
        except Exception as e:
            logger.error(f"HomeHub: Failed to get temp stats: {e}")
            return {}
    
    async def start_temp_logging(self):
        """Start the background temperature logging task"""
        if self._temp_log_task is not None:
            return
        
        async def log_loop():
            while True:
                interval = self.settings.get('temp_logging_interval', 1)
                # Clamp to 1-5 minutes
                interval = max(1, min(5, interval))
                await asyncio.sleep(interval * 60)
                self._log_temperature_readings()
        
        self._temp_log_task = asyncio.create_task(log_loop())
        logger.info("HomeHub: Temperature logging started")
    
    def stop_temp_logging(self):
        """Stop the background temperature logging task"""
        if self._temp_log_task:
            self._temp_log_task.cancel()
            self._temp_log_task = None
            logger.info("HomeHub: Temperature logging stopped")
    
    def _load_settings(self):
        """Load home hub settings from config file"""
        try:
            config_path = Path("/home/admin/wallclock/homehub_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    saved = json.load(f)
                    self.settings.update(saved.get('settings', {}))
                    self.automations = saved.get('automations', [])
                    self.scenes = saved.get('scenes', [])
                logger.info("HomeHub: Loaded settings from config")
        except Exception as e:
            logger.warning(f"HomeHub: Could not load settings: {e}")
    
    def _save_settings(self):
        """Save home hub settings to config file"""
        try:
            config_path = Path("/home/admin/wallclock/homehub_config.json")
            with open(config_path, 'w') as f:
                json.dump({
                    'settings': self.settings,
                    'automations': self.automations,
                    'scenes': self.scenes
                }, f, indent=2)
            logger.info("HomeHub: Settings saved")
        except Exception as e:
            logger.error(f"HomeHub: Could not save settings: {e}")
    
    def _add_log(self, level: str, message: str):
        """Add entry to event log"""
        from datetime import datetime
        entry = {
            'time': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        self.event_log.insert(0, entry)
        # Keep only last 200 entries
        if len(self.event_log) > 200:
            self.event_log = self.event_log[:200]
        
        if self.settings.get('log_events', True):
            logger.info(f"HomeHub [{level}]: {message}")
    
    async def connect_mqtt(self) -> bool:
        """Connect to MQTT broker"""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("HomeHub: paho-mqtt not installed")
            self._add_log('error', 'paho-mqtt library not installed')
            return False
        
        try:
            self._add_log('info', f"Connecting to MQTT broker at {self.settings['mqtt_host']}:{self.settings['mqtt_port']}")
            
            self.mqtt_client = mqtt.Client(client_id="wallclock-homehub")
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Set credentials if provided
            if self.settings.get('mqtt_username'):
                self.mqtt_client.username_pw_set(
                    self.settings['mqtt_username'],
                    self.settings.get('mqtt_password', '')
                )
            
            # Connect (non-blocking)
            self.mqtt_client.connect_async(
                self.settings['mqtt_host'],
                self.settings['mqtt_port'],
                keepalive=60
            )
            self.mqtt_client.loop_start()
            
            # Wait a bit for connection
            await asyncio.sleep(2)
            return self.connected
            
        except Exception as e:
            logger.error(f"HomeHub: MQTT connection error: {e}")
            self._add_log('error', f'MQTT connection failed: {str(e)}')
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT"""
        if rc == 0:
            self.connected = True
            self._add_log('info', 'Connected to MQTT broker')
            
            # Subscribe to Zigbee2MQTT topics
            topic = self.settings['z2m_topic']
            client.subscribe(f"{topic}/bridge/state")
            client.subscribe(f"{topic}/bridge/devices")
            client.subscribe(f"{topic}/bridge/event")
            client.subscribe(f"{topic}/bridge/response/#")
            client.subscribe(f"{topic}/+")  # Device state updates
            
            # Request device list
            client.publish(f"{topic}/bridge/request/devices", "")
            
            logger.info("HomeHub: MQTT connected and subscribed")
        else:
            self.connected = False
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            msg = error_messages.get(rc, f"Unknown error ({rc})")
            self._add_log('error', f'MQTT connection failed: {msg}')
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT"""
        self.connected = False
        if rc != 0:
            self._add_log('warn', f'MQTT disconnected unexpectedly (code {rc})')
        else:
            self._add_log('info', 'MQTT disconnected')
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback when MQTT message received"""
        try:
            topic = msg.topic
            base_topic = self.settings['z2m_topic']
            
            # Bridge state
            if topic == f"{base_topic}/bridge/state":
                payload = msg.payload.decode()
                self._add_log('info', f'Zigbee2MQTT state: {payload}')
            
            # Device list
            elif topic == f"{base_topic}/bridge/devices":
                devices = json.loads(msg.payload.decode())
                self._process_device_list(devices)
            
            # Bridge events (device joined, left, etc)
            elif topic == f"{base_topic}/bridge/event":
                event = json.loads(msg.payload.decode())
                self._process_bridge_event(event)
            
            # Device state updates
            elif topic.startswith(f"{base_topic}/") and not topic.startswith(f"{base_topic}/bridge"):
                device_name = topic.replace(f"{base_topic}/", "")
                if device_name and msg.payload:
                    try:
                        state = json.loads(msg.payload.decode())
                        self.device_states[device_name] = state
                        self._add_log('info', f'Device {device_name} state updated')
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"HomeHub: Error processing MQTT message: {e}")
    
    def _process_device_list(self, devices: list):
        """Process device list from Zigbee2MQTT"""
        self.devices = {}
        for device in devices:
            if device.get('type') != 'Coordinator':
                ieee = device.get('ieee_address', '')
                friendly_name = device.get('friendly_name', ieee)
                
                # Determine device type from definition
                definition = device.get('definition') or {}
                device_type = self._determine_device_type(definition)
                
                self.devices[ieee] = {
                    'ieee_address': ieee,
                    'friendly_name': friendly_name,
                    'type': device_type,
                    'model': definition.get('model', 'Unknown'),
                    'manufacturer': definition.get('vendor', 'Unknown'),
                    'description': definition.get('description', ''),
                    'available': device.get('interviewing', False) == False,
                    'state': self.device_states.get(friendly_name, {})
                }
        
        self._add_log('info', f'Loaded {len(self.devices)} devices')
    
    def _determine_device_type(self, definition: dict) -> str:
        """Determine device type from Zigbee2MQTT definition"""
        exposes = definition.get('exposes', [])
        
        # Collect all exposed properties
        all_properties = set()
        
        for expose in exposes:
            if isinstance(expose, dict):
                exp_type = expose.get('type', '')
                
                # Check device-specific types first
                if exp_type == 'light':
                    return 'light'
                elif exp_type == 'switch':
                    return 'switch'
                elif exp_type == 'lock':
                    return 'lock'
                elif exp_type == 'cover':
                    return 'cover'
                elif exp_type == 'fan':
                    return 'fan'
                elif exp_type == 'climate':
                    return 'thermostat'
                
                # Collect property names
                prop = expose.get('property', '') or expose.get('name', '')
                if prop:
                    all_properties.add(prop)
                
                # Also check for nested features
                features = expose.get('features', [])
                if isinstance(features, list):
                    for f in features:
                        if isinstance(f, dict):
                            feat_prop = f.get('property', '') or f.get('name', '')
                            if feat_prop:
                                all_properties.add(feat_prop)
        
        # Categorize by properties
        # Button devices have 'action' property
        if 'action' in all_properties:
            return 'button'
        
        # Contact sensors (door/window) have 'contact' property
        if 'contact' in all_properties:
            return 'contact'
        
        # Motion/occupancy sensors
        if 'occupancy' in all_properties:
            return 'motion'
        
        # Vibration sensors
        if 'vibration' in all_properties:
            return 'vibration'
        
        # Temperature/humidity sensors
        sensor_properties = ['temperature', 'humidity', 'pressure', 'illuminance', 
                           'water_leak', 'smoke', 'gas', 'battery', 'power']
        if any(prop in all_properties for prop in sensor_properties):
            return 'sensor'
        
        return 'unknown'
    
    def _process_bridge_event(self, event: dict):
        """Process bridge events (device joined, left, etc)"""
        event_type = event.get('type', '')
        data = event.get('data', {})
        
        if event_type == 'device_joined':
            friendly_name = data.get('friendly_name', 'Unknown')
            self._add_log('info', f'Device joined: {friendly_name}')
            # Request updated device list
            if self.mqtt_client:
                self.mqtt_client.publish(f"{self.settings['z2m_topic']}/bridge/request/devices", "")
        
        elif event_type == 'device_leave':
            friendly_name = data.get('friendly_name', 'Unknown')
            self._add_log('warn', f'Device left: {friendly_name}')
        
        elif event_type == 'device_announce':
            friendly_name = data.get('friendly_name', 'Unknown')
            self._add_log('info', f'Device announced: {friendly_name}')
    
    def get_status(self) -> dict:
        """Get current home hub status"""
        # Check if Zigbee2MQTT is likely running
        z2m_running = False
        try:
            import subprocess
            result = subprocess.run(['pgrep', '-f', 'zigbee2mqtt'], capture_output=True, timeout=5)
            z2m_running = result.returncode == 0
        except:
            pass
        
        if self.connected:
            return {
                'status': 'online',
                'message': 'Connected to Zigbee2MQTT',
                'device_count': len(self.devices),
                'permit_join': self.permit_join_active
            }
        elif z2m_running:
            return {
                'status': 'connecting',
                'message': 'Zigbee2MQTT running, connecting to MQTT...'
            }
        else:
            return {
                'status': 'not_configured',
                'message': 'Zigbee2MQTT not running. Please set up Zigbee2MQTT first.'
            }
    
    def get_devices(self) -> list:
        """Get list of all devices with their current states"""
        import sqlite3
        
        # Get latest readings from database for each device
        latest_readings = {}
        try:
            conn = sqlite3.connect(str(self.temp_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get most recent reading for each device
            cursor.execute('''
                SELECT t1.* FROM temp_readings t1
                INNER JOIN (
                    SELECT device_id, MAX(timestamp) as max_ts
                    FROM temp_readings
                    GROUP BY device_id
                ) t2 ON t1.device_id = t2.device_id AND t1.timestamp = t2.max_ts
            ''')
            
            for row in cursor.fetchall():
                latest_readings[row['device_id']] = {
                    'temperature': row['temperature'],
                    'humidity': row['humidity'],
                    'pressure': row['pressure'],
                    'battery': row['battery'],
                    'linkquality': row['linkquality']
                }
            conn.close()
        except Exception as e:
            logger.warning(f"HomeHub: Could not fetch latest readings: {e}")
        
        devices = []
        for ieee, device in self.devices.items():
            # Start with cached MQTT state
            state = self.device_states.get(device['friendly_name'], {}).copy()
            
            # If we have database readings, use them as fallback or supplement
            if ieee in latest_readings:
                db_reading = latest_readings[ieee]
                # Use database values if not in MQTT state
                if 'temperature' not in state and db_reading.get('temperature') is not None:
                    state['temperature'] = db_reading['temperature']
                if 'humidity' not in state and db_reading.get('humidity') is not None:
                    state['humidity'] = db_reading['humidity']
                if 'pressure' not in state and db_reading.get('pressure') is not None:
                    state['pressure'] = db_reading['pressure']
                if 'battery' not in state and db_reading.get('battery') is not None:
                    state['battery'] = db_reading['battery']
                if 'linkquality' not in state and db_reading.get('linkquality') is not None:
                    state['linkquality'] = db_reading['linkquality']
            
            device['state'] = state
            devices.append(device)
        return devices
    
    def permit_join(self, duration: int = 120) -> bool:
        """Enable/disable permit join mode"""
        if not self.mqtt_client or not self.connected:
            return False
        
        try:
            topic = f"{self.settings['z2m_topic']}/bridge/request/permit_join"
            payload = json.dumps({'value': duration > 0, 'time': duration})
            self.mqtt_client.publish(topic, payload)
            
            self.permit_join_active = duration > 0
            
            if duration > 0:
                self._add_log('info', f'Permit join enabled for {duration} seconds')
            else:
                self._add_log('info', 'Permit join disabled')
            
            return True
        except Exception as e:
            logger.error(f"HomeHub: Error setting permit join: {e}")
            return False
    
    def send_device_command(self, device_id: str, command: dict) -> bool:
        """Send command to a device"""
        if not self.mqtt_client or not self.connected:
            return False
        
        try:
            # Find device by IEEE or friendly name
            device = None
            for d in self.devices.values():
                if d['ieee_address'] == device_id or d['friendly_name'] == device_id:
                    device = d
                    break
            
            if not device:
                return False
            
            topic = f"{self.settings['z2m_topic']}/{device['friendly_name']}/set"
            self.mqtt_client.publish(topic, json.dumps(command))
            
            self._add_log('info', f"Command sent to {device['friendly_name']}: {command}")
            return True
        except Exception as e:
            logger.error(f"HomeHub: Error sending command: {e}")
            return False
    
    def refresh_device(self, device_id: str) -> bool:
        """
        Query a device to force it to report its current state.
        Sends a 'get' request to the device via Zigbee2MQTT.
        """
        if not self.mqtt_client or not self.connected:
            return False
        
        try:
            # Find device by IEEE or friendly name
            device = None
            for d in self.devices.values():
                if d['ieee_address'] == device_id or d['friendly_name'] == device_id:
                    device = d
                    break
            
            if not device:
                return False
            
            # Send get request - empty strings mean "report current value"
            # For sensors, request common attributes
            get_payload = {
                "temperature": "",
                "humidity": "",
                "pressure": "",
                "battery": ""
            }
            
            topic = f"{self.settings['z2m_topic']}/{device['friendly_name']}/get"
            self.mqtt_client.publish(topic, json.dumps(get_payload))
            
            self._add_log('info', f"Refresh requested for {device['friendly_name']}")
            return True
        except Exception as e:
            logger.error(f"HomeHub: Error refreshing device: {e}")
            return False
    
    def refresh_all_devices(self) -> int:
        """Refresh all devices, returns count of devices queried"""
        count = 0
        for ieee in self.devices.keys():
            if self.refresh_device(ieee):
                count += 1
        return count
    
    def remove_device(self, device_id: str, force: bool = True) -> bool:
        """
        Remove a device from the network.
        
        Args:
            device_id: IEEE address or friendly name
            force: If True, remove even if device is unresponsive (default True)
                   Unresponsive devices (didn't complete interview, battery dead, etc)
                   require force=True to be removed.
        """
        if not self.mqtt_client or not self.connected:
            return False
        
        try:
            topic = f"{self.settings['z2m_topic']}/bridge/request/device/remove"
            payload = json.dumps({'id': device_id, 'force': force})
            self.mqtt_client.publish(topic, payload)
            
            # Also remove from local cache immediately
            to_remove = None
            for ieee, device in self.devices.items():
                if ieee == device_id or device.get('friendly_name') == device_id:
                    to_remove = ieee
                    break
            if to_remove:
                del self.devices[to_remove]
            
            self._add_log('info', f'Requested removal of device: {device_id} (force={force})')
            return True
        except Exception as e:
            logger.error(f"HomeHub: Error removing device: {e}")
            return False
    
    def rename_device(self, device_id: str, new_name: str) -> bool:
        """Rename a device"""
        if not self.mqtt_client or not self.connected:
            return False
        
        try:
            topic = f"{self.settings['z2m_topic']}/bridge/request/device/rename"
            payload = json.dumps({'from': device_id, 'to': new_name})
            self.mqtt_client.publish(topic, payload)
            
            self._add_log('info', f'Requested rename: {device_id} -> {new_name}')
            return True
        except Exception as e:
            logger.error(f"HomeHub: Error renaming device: {e}")
            return False
    
    def update_settings(self, new_settings: dict):
        """Update home hub settings"""
        self.settings.update(new_settings)
        self._save_settings()
        self._add_log('info', 'Settings updated')
    
    def disconnect(self):
        """Disconnect from MQTT"""
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
            self.mqtt_client = None
            self.connected = False


# Initialize Home Hub Manager
homehub_manager = HomeHubManager()


# ============================================================================
# HOME HUB API ENDPOINTS
# ============================================================================

@app.get("/homehub")
async def homehub_page():
    """Serve the Home Hub management page"""
    return FileResponse("frontend/homehub.html")


@app.get("/api/homehub/status")
async def homehub_status():
    """Get Home Hub / Zigbee status"""
    return homehub_manager.get_status()


@app.get("/api/homehub/devices")
async def homehub_devices():
    """Get all Zigbee devices"""
    return {
        'devices': homehub_manager.get_devices(),
        'count': len(homehub_manager.devices)
    }


@app.post("/api/homehub/permit-join")
async def homehub_permit_join(request: Request):
    """Enable/disable device pairing mode"""
    try:
        data = await request.json()
        duration = data.get('duration', 120)
        
        success = homehub_manager.permit_join(duration)
        
        if success:
            return {'success': True, 'message': f'Permit join {"enabled" if duration > 0 else "disabled"}'}
        else:
            return {'success': False, 'message': 'Failed to set permit join. Is Zigbee2MQTT running?'}
    except Exception as e:
        logger.error(f"HomeHub API error: {e}")
        return {'success': False, 'message': str(e)}


@app.post("/api/homehub/devices/{device_id}/command")
async def homehub_device_command(device_id: str, request: Request):
    """Send command to a device"""
    try:
        command = await request.json()
        success = homehub_manager.send_device_command(device_id, command)
        
        if success:
            return {'success': True}
        else:
            return {'success': False, 'message': 'Failed to send command'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


@app.post("/api/homehub/devices/{device_id}/refresh")
async def homehub_refresh_device(device_id: str):
    """Query a device to force it to report current state"""
    success = homehub_manager.refresh_device(device_id)
    
    if success:
        return {'success': True, 'message': 'Refresh requested'}
    else:
        return {'success': False, 'message': 'Failed to refresh device'}


@app.post("/api/homehub/devices/refresh-all")
async def homehub_refresh_all_devices():
    """Query all devices to force them to report current state"""
    count = homehub_manager.refresh_all_devices()
    return {'success': True, 'count': count, 'message': f'Refresh requested for {count} devices'}


@app.delete("/api/homehub/devices/{device_id}")
async def homehub_remove_device(device_id: str, force: bool = True):
    """
    Remove a device from the network.
    
    Args:
        device_id: IEEE address or friendly name
        force: Force removal even if device is unresponsive (default: True)
    """
    success = homehub_manager.remove_device(device_id, force=force)
    
    if success:
        return {'success': True, 'message': f'Device removal requested (force={force})'}
    else:
        return {'success': False, 'message': 'Failed to remove device'}


@app.post("/api/homehub/devices/{device_id}/rename")
async def homehub_rename_device(device_id: str, request: Request):
    """Rename a device"""
    try:
        data = await request.json()
        new_name = data.get('name', '')
        
        if not new_name:
            return {'success': False, 'message': 'Name required'}
        
        success = homehub_manager.rename_device(device_id, new_name)
        
        if success:
            return {'success': True}
        else:
            return {'success': False, 'message': 'Failed to rename device'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


@app.get("/api/homehub/settings")
async def homehub_get_settings():
    """Get Home Hub settings"""
    return {
        'settings': homehub_manager.settings,
        'automations': homehub_manager.automations,
        'scenes': homehub_manager.scenes
    }


@app.post("/api/homehub/settings")
async def homehub_save_settings(request: Request):
    """Save Home Hub settings"""
    try:
        new_settings = await request.json()
        homehub_manager.update_settings(new_settings)
        
        # Reconnect MQTT if settings changed
        if homehub_manager.connected:
            homehub_manager.disconnect()
            await homehub_manager.connect_mqtt()
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}


@app.get("/api/homehub/logs")
async def homehub_logs():
    """Get Home Hub event logs"""
    return {'logs': homehub_manager.event_log}


@app.delete("/api/homehub/logs")
async def homehub_clear_logs():
    """Clear Home Hub event logs"""
    homehub_manager.event_log = []
    return {'success': True}


@app.get("/api/homehub/network")
async def homehub_network_info():
    """Get Zigbee network information"""
    return {
        'coordinator': {
            'status': 'online' if homehub_manager.connected else 'offline',
            'device_count': len(homehub_manager.devices)
        },
        'permit_join': homehub_manager.permit_join_active
    }


# ============================================================================
# TEMPERATURE HISTORY API
# ============================================================================

@app.get("/api/homehub/temp-history")
async def get_temp_history(device_id: str = None, hours: int = 24):
    """Get temperature history for all or specific device"""
    history = homehub_manager.get_temp_history(device_id, hours)
    return {'history': history, 'count': len(history)}

@app.get("/api/homehub/temp-history/{device_id}")
async def get_device_temp_history(device_id: str, hours: int = 24):
    """Get temperature history for a specific device"""
    history = homehub_manager.get_temp_history(device_id, hours)
    stats = homehub_manager.get_temp_stats(device_id, hours)
    return {
        'device_id': device_id,
        'history': history,
        'stats': stats,
        'count': len(history)
    }

@app.get("/api/homehub/temp-stats/{device_id}")
async def get_device_temp_stats(device_id: str, hours: int = 24):
    """Get temperature statistics for a device"""
    stats = homehub_manager.get_temp_stats(device_id, hours)
    return {'device_id': device_id, 'hours': hours, 'stats': stats}

@app.get("/api/homehub/temp-settings")
async def get_temp_settings():
    """Get temperature logging settings"""
    return {
        'enabled': homehub_manager.settings.get('temp_logging_enabled', True),
        'interval': homehub_manager.settings.get('temp_logging_interval', 1)
    }

@app.post("/api/homehub/temp-settings")
async def update_temp_settings(request: Request):
    """Update temperature logging settings"""
    data = await request.json()
    
    if 'enabled' in data:
        homehub_manager.settings['temp_logging_enabled'] = bool(data['enabled'])
    
    if 'interval' in data:
        # Clamp interval to 1-5 minutes
        interval = max(1, min(5, int(data['interval'])))
        homehub_manager.settings['temp_logging_interval'] = interval
    
    homehub_manager._save_settings()
    
    return {
        'success': True,
        'enabled': homehub_manager.settings.get('temp_logging_enabled', True),
        'interval': homehub_manager.settings.get('temp_logging_interval', 1)
    }

@app.post("/api/homehub/temp-log-now")
async def trigger_temp_log():
    """Manually trigger a temperature log"""
    homehub_manager._log_temperature_readings()
    return {'success': True, 'message': 'Temperature readings logged'}


# ============================================================================
# AC HUB - HVAC Monitoring & Method C Detection
# ============================================================================

class ACHubManager:
    """
    Manages AC compressor detection using Method C (ΔT-based detection).
    Tracks runtime, cycles, and provides cost estimation.
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        # Detection thresholds (Method C - ΔT based)
        'dt_on': 14.0,           # °F - ΔT threshold to detect ON
        'dt_off': 10.0,          # °F - ΔT threshold to detect OFF
        'min_on_sec': 180,       # Minimum ON duration to count
        'min_off_sec': 180,      # Minimum OFF gap to count as separate
        'start_confirm_sec': 120, # Time ΔT must stay above threshold
        'stop_confirm_sec': 120,  # Time ΔT must stay below threshold
        'max_gap_sec': 900,      # Max gap before treating as missing data
        
        # SAT-based detection (additional ON/OFF signals)
        'sat_low_threshold': 65.0,       # °F - SAT below this suggests cooling
        'sat_stable_confirm_sec': 120,   # Time SAT must stay low/stable to confirm ON (2 min)
        'sat_rise_delta': 3.0,           # °F - SAT rise from baseline to trigger OFF
        'sat_stability_tolerance': 1.0,  # °F - SAT variance tolerance for "stable"
        'sat_detection_enabled': True,   # Enable SAT-based detection alongside ΔT
        
        # EMA smoothing
        'smoothing_enabled': True,
        'smoothing_tau': 300,    # Time constant in seconds (5 min)
        
        # OAT gating
        'oat_gating_enabled': False,
        'oat_cool_min': 60.0,    # °F - minimum OAT for cooling detection
        
        # Sensor mapping (friendly names)
        'rat_sensor': 'Return Temp',      # Return Air Temperature
        'sat_sensor': 'AC Supply Temp',   # Supply Air Temperature  
        'oat_sensor': None,               # Outdoor Air Temperature (optional)
        'window_sensor': None,            # Window open sensor (optional)
        
        # Budget/cost settings
        'ac_kw_running': 3.5,    # kW when compressor is running
        'rate_per_kwh': 0.12,    # $/kWh (normal/off-peak rate)
        'peak_rate_per_kwh': 0.25,  # $/kWh (peak rate)
        'peak_start_hour': 14,   # Peak pricing starts (2 PM)
        'peak_end_hour': 19,     # Peak pricing ends (7 PM)
        'peak_enabled': False,   # Whether to use peak pricing
        'tbase': 65.0,           # Base temp for CDD calculation
        'exclude_windows_open': False,
        
        # Display
        'temp_unit': 'F',         # F or C
        
        # Server Watts → Cooling Cost settings
        'server_watts_enabled': True,
        'efficiency_mode': None,           # 'COP', 'EER', or 'MULTIPLIER' (user must select)
        'cop_value': None,                 # Coefficient of Performance (e.g., 3.0-5.0 typical)
        'eer_value': None,                 # Energy Efficiency Ratio (BTU/W-hr, e.g., 10-15)
        'kw_per_kw_heat': None,            # Dimensionless multiplier (≈ 1/COP)
        'server_gating_mode': 'BOTH',      # 'THERMO_EQUIV', 'SAT_GATED', or 'BOTH'
        'server_sat_gating_threshold': 65.0,  # °F - AC is running when SAT <= this
        'server_exclude_windows_open': False,
        'server_max_gap_sec': 900,         # Max gap for integration (15 min default)
        'server_watts_sensor': None,       # Zigbee sensor for server power (friendly name)
        'server_window_sensor': None       # Zigbee sensor for window open (friendly name)
    }
    
    def __init__(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self.db_path = Path("/home/admin/wallclock/achub.db")
        self._init_db()
        self._load_config()
        
        # Current state
        self.current_state = 'UNKNOWN'  # ON, OFF, UNKNOWN
        self.candidate_state = None
        self.candidate_start_time = None
        self.last_ema_dt = None
        self.last_sample_time = None
        self.current_run_start = None
    
    def _celsius_to_fahrenheit(self, temp_c: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return (temp_c * 9/5) + 32
        
    def _init_db(self):
        """Initialize SQLite database for AC state tracking"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # AC state history (for charting state over time)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ac_state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    state TEXT NOT NULL,
                    delta_t REAL,
                    ema_delta_t REAL,
                    rat REAL,
                    sat REAL,
                    oat REAL,
                    window_open INTEGER DEFAULT 0
                )
            ''')
            
            # Runtime aggregates (daily summaries)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ac_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    runtime_on_sec INTEGER DEFAULT 0,
                    runtime_off_sec INTEGER DEFAULT 0,
                    cycle_count INTEGER DEFAULT 0,
                    runtime_windows_open_sec INTEGER DEFAULT 0,
                    runtime_windows_closed_sec INTEGER DEFAULT 0,
                    cycles_windows_open INTEGER DEFAULT 0,
                    cycles_windows_closed INTEGER DEFAULT 0,
                    avg_delta_t REAL,
                    max_delta_t REAL,
                    avg_oat REAL,
                    cdd_proxy REAL DEFAULT 0,
                    missing_gap_sec INTEGER DEFAULT 0
                )
            ''')
            
            # Individual run records
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ac_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    duration_sec INTEGER,
                    window_open INTEGER DEFAULT 0,
                    ignored INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_state_time ON ac_state_history(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON ac_daily_stats(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_runs_start ON ac_runs(start_time)')
            
            # Server watts readings (for server → cooling cost tracking)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_watts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    watts REAL NOT NULL,
                    source TEXT DEFAULT 'manual'
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_server_watts_time ON server_watts(timestamp)')
            
            # Server cooling cost history (computed values)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_cooling_cost (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    server_watts REAL,
                    heat_btu_hr REAL,
                    heat_kw REAL,
                    electrical_kw REAL,
                    cost_rate_per_hr REAL,
                    ac_state TEXT,
                    window_open INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_server_cost_time ON server_cooling_cost(timestamp)')
            
            conn.commit()
            conn.close()
            logger.info("ACHub: Database initialized")
        except Exception as e:
            logger.error(f"ACHub: Failed to init database: {e}")
    
    def _load_config(self):
        """Load AC Hub config from file"""
        try:
            config_path = Path("/home/admin/wallclock/achub_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    saved = json.load(f)
                    self.config.update(saved)
                logger.info("ACHub: Config loaded")
        except Exception as e:
            logger.warning(f"ACHub: Could not load config: {e}")
    
    def _save_config(self):
        """Save AC Hub config to file"""
        try:
            config_path = Path("/home/admin/wallclock/achub_config.json")
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("ACHub: Config saved")
        except Exception as e:
            logger.error(f"ACHub: Could not save config: {e}")
    
    def get_config(self) -> dict:
        """Get current configuration"""
        return self.config.copy()
    
    def update_config(self, new_config: dict):
        """Update configuration"""
        self.config.update(new_config)
        self._save_config()
    
    def _get_sensor_readings(self, hours: int = 24) -> list:
        """Get temperature readings from the temp_history database"""
        import sqlite3
        from datetime import datetime, timedelta
        readings = []
        try:
            conn = sqlite3.connect('/home/admin/wallclock/temp_history.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get sensor names from config
            rat_sensor = self.config.get('rat_sensor', 'Return Temp')
            sat_sensor = self.config.get('sat_sensor', 'AC Supply Temp')
            oat_sensor = self.config.get('oat_sensor')
            
            # Get all readings
            cursor.execute('''
                SELECT timestamp, friendly_name, temperature
                FROM temp_readings
                WHERE timestamp > datetime('now', ?)
                AND friendly_name IN (?, ?, ?)
                ORDER BY timestamp ASC
            ''', (f'-{hours} hours', rat_sensor, sat_sensor, oat_sensor or ''))
            
            # Group readings by time bucket (round to nearest minute)
            from collections import defaultdict
            time_buckets = defaultdict(dict)
            
            for row in cursor.fetchall():
                ts_str = row['timestamp']
                name = row['friendly_name']
                temp = row['temperature']
                
                # Parse timestamp and round to nearest minute for grouping
                try:
                    ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    # Round to nearest minute
                    bucket_ts = ts.replace(second=0)
                    bucket_key = bucket_ts.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    bucket_key = ts_str
                
                if name == rat_sensor:
                    time_buckets[bucket_key]['rat'] = temp
                    time_buckets[bucket_key]['timestamp'] = ts_str
                elif name == sat_sensor:
                    time_buckets[bucket_key]['sat'] = temp
                    if 'timestamp' not in time_buckets[bucket_key]:
                        time_buckets[bucket_key]['timestamp'] = ts_str
                elif oat_sensor and name == oat_sensor:
                    time_buckets[bucket_key]['oat'] = temp
            
            conn.close()
            
            # Helper to convert Celsius to Fahrenheit
            def c_to_f(c):
                return (c * 9/5) + 32 if c is not None else None
            
            # Get current window status (we'll apply to most recent readings)
            # Note: For historical accuracy, we'd need to log window state over time
            current_window_open = self._get_window_open_status()
            
            # Convert to list and sort, converting temps to Fahrenheit
            for bucket_key, data in sorted(time_buckets.items()):
                if 'rat' in data and 'sat' in data:
                    readings.append({
                        'timestamp': data['timestamp'],
                        'rat': c_to_f(data['rat']),
                        'sat': c_to_f(data['sat']),
                        'oat': c_to_f(data.get('oat')),
                        'window_open': current_window_open  # Use current state
                    })
            
        except Exception as e:
            logger.error(f"ACHub: Failed to get sensor readings: {e}")
        
        return readings
    
    def _compute_ema(self, current_dt: float, dt_seconds: float) -> float:
        """Compute time-based exponential moving average"""
        if not self.config.get('smoothing_enabled', True):
            return current_dt
        
        if self.last_ema_dt is None:
            return current_dt
        
        tau = self.config.get('smoothing_tau', 300)
        alpha = 1 - math.exp(-dt_seconds / tau)
        return alpha * current_dt + (1 - alpha) * self.last_ema_dt
    
    def _check_oat_gating(self, oat: float) -> bool:
        """Check if OAT gating allows detection"""
        if not self.config.get('oat_gating_enabled', False):
            return True  # No gating, always allow
        
        if oat is None:
            return True  # No OAT data, allow detection
        
        return oat >= self.config.get('oat_cool_min', 60.0)
    
    def compute_ac_state(self, samples: list, config: dict = None) -> dict:
        """
        Compute AC compressor state from sensor samples using Method C.
        
        Args:
            samples: List of {timestamp, rat, sat, oat?, window_open?}
            config: Optional override config
        
        Returns:
            Dict with state_timeline, aggregates, etc.
        """
        if config is None:
            config = self.config
        
        # Extract thresholds (ΔT-based)
        dt_on = config.get('dt_on', 14.0)
        dt_off = config.get('dt_off', 10.0)
        start_confirm_sec = config.get('start_confirm_sec', 120)
        stop_confirm_sec = config.get('stop_confirm_sec', 120)
        min_on_sec = config.get('min_on_sec', 180)
        min_off_sec = config.get('min_off_sec', 180)
        max_gap_sec = config.get('max_gap_sec', 900)
        
        # SAT-based detection thresholds
        sat_low_threshold = config.get('sat_low_threshold', 65.0)
        sat_stable_confirm_sec = config.get('sat_stable_confirm_sec', 120)
        sat_rise_delta = config.get('sat_rise_delta', 3.0)
        sat_stability_tolerance = config.get('sat_stability_tolerance', 1.0)
        sat_detection_enabled = config.get('sat_detection_enabled', True)
        
        # State tracking (ΔT-based)
        current_state = 'OFF'
        candidate_state = None
        candidate_start_time = None
        last_ema = None
        last_time = None
        
        # State tracking (SAT-based)
        sat_low_start_time = None      # When SAT first went below threshold
        sat_baseline = None            # Stable SAT value when AC is running
        sat_baseline_samples = []      # Recent SAT values for stability check
        
        # Results
        state_timeline = []
        runs = []  # List of {start, end, duration, window_open}
        current_run_start = None
        
        # Aggregates
        runtime_on_sec = 0
        runtime_off_sec = 0
        missing_sec = 0
        runtime_windows_open = 0
        runtime_windows_closed = 0
        delta_t_values = []
        
        for sample in samples:
            ts_str = sample['timestamp']
            rat = sample['rat']
            sat = sample['sat']
            oat = sample.get('oat')
            window_open = sample.get('window_open', False)
            
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            
            # Compute ΔT
            delta_t = rat - sat
            delta_t_values.append(delta_t)
            
            # Compute EMA
            if last_time is not None:
                dt_seconds = (ts - last_time).total_seconds()
                
                # Handle missing gaps
                if dt_seconds > max_gap_sec:
                    missing_sec += dt_seconds
                    # Reset EMA on large gaps
                    ema_dt = delta_t
                else:
                    ema_dt = self._compute_ema_static(delta_t, dt_seconds, last_ema, config)
                    
                    # Accumulate runtime
                    if current_state == 'ON':
                        runtime_on_sec += dt_seconds
                        if window_open:
                            runtime_windows_open += dt_seconds
                        else:
                            runtime_windows_closed += dt_seconds
                    else:
                        runtime_off_sec += dt_seconds
            else:
                ema_dt = delta_t
                dt_seconds = 0
            
            # Check OAT gating
            detection_enabled = self._check_oat_gating(oat)
            
            if not detection_enabled:
                state = 'UNKNOWN'
            else:
                # =============================================================
                # SAT-based detection logic (additional ON/OFF signals)
                # =============================================================
                sat_triggered_on = False
                sat_triggered_off = False
                
                if sat_detection_enabled:
                    # Track SAT stability for baseline
                    sat_baseline_samples.append(sat)
                    if len(sat_baseline_samples) > 10:  # Keep last 10 samples
                        sat_baseline_samples.pop(0)
                    
                    # Check if SAT is below threshold
                    if sat < sat_low_threshold:
                        # SAT is low - potential AC running
                        if sat_low_start_time is None:
                            sat_low_start_time = ts
                            sat_baseline = sat
                        
                        # Check if SAT has been stable and low for confirmation time
                        sat_low_duration = (ts - sat_low_start_time).total_seconds()
                        
                        # Calculate SAT stability (variance)
                        if len(sat_baseline_samples) >= 3:
                            sat_avg = sum(sat_baseline_samples) / len(sat_baseline_samples)
                            sat_variance = max(sat_baseline_samples) - min(sat_baseline_samples)
                            
                            # Update baseline to current stable value
                            if sat_variance <= sat_stability_tolerance:
                                sat_baseline = sat_avg
                        
                        # SAT-based ON trigger:
                        # SAT < threshold, stable for confirm time
                        # UNLESS: window is OPEN AND OAT < 65 (cold outside air causing low SAT)
                        cold_outside_with_window = window_open and oat is not None and oat < sat_low_threshold
                        
                        if sat_low_duration >= sat_stable_confirm_sec and not cold_outside_with_window:
                            sat_triggered_on = True
                    
                    else:
                        # SAT rose above threshold
                        # Check for SAT-based OFF trigger:
                        # SAT was low and stable, now rose by sat_rise_delta
                        # ONLY IF: window is CLOSED AND OAT > 65
                        if sat_baseline is not None and sat_low_start_time is not None:
                            sat_rise = sat - sat_baseline
                            warm_outside_window_closed = (not window_open) and (oat is None or oat > sat_low_threshold)
                            
                            if sat_rise >= sat_rise_delta and warm_outside_window_closed:
                                sat_triggered_off = True
                        
                        # Reset SAT tracking when SAT goes above threshold
                        sat_low_start_time = None
                        sat_baseline = None
                
                # =============================================================
                # Combined state machine (ΔT + SAT)
                # =============================================================
                if current_state == 'OFF':
                    # Check for ON transition
                    # Method 1: ΔT-based (EMA ΔT >= threshold for confirm time)
                    dt_wants_on = False
                    if ema_dt >= dt_on:
                        if candidate_state != 'ON':
                            candidate_state = 'ON'
                            candidate_start_time = ts
                        elif (ts - candidate_start_time).total_seconds() >= start_confirm_sec:
                            dt_wants_on = True
                    else:
                        if candidate_state == 'ON':
                            candidate_state = None
                            candidate_start_time = None
                    
                    # Transition to ON if either method triggers
                    if dt_wants_on or sat_triggered_on:
                        current_state = 'ON'
                        current_run_start = candidate_start_time if candidate_start_time else ts
                        candidate_state = None
                        candidate_start_time = None
                
                elif current_state == 'ON':
                    # Check for OFF transition
                    # Method 1: ΔT-based (EMA ΔT <= threshold for confirm time)
                    dt_wants_off = False
                    if ema_dt <= dt_off:
                        if candidate_state != 'OFF':
                            candidate_state = 'OFF'
                            candidate_start_time = ts
                        elif (ts - candidate_start_time).total_seconds() >= stop_confirm_sec:
                            dt_wants_off = True
                    else:
                        if candidate_state == 'OFF':
                            candidate_state = None
                            candidate_start_time = None
                    
                    # Transition to OFF if either method triggers
                    if dt_wants_off or sat_triggered_off:
                        run_end_time = candidate_start_time if candidate_start_time else ts
                        run_duration = (run_end_time - current_run_start).total_seconds() if current_run_start else 0
                        runs.append({
                            'start': current_run_start.isoformat() if current_run_start else ts.isoformat(),
                            'end': run_end_time.isoformat(),
                            'duration_sec': run_duration,
                            'window_open': window_open,
                            'ignored': run_duration < min_on_sec
                        })
                        current_state = 'OFF'
                        current_run_start = None
                        candidate_state = None
                        candidate_start_time = None
                
                state = current_state
            
            # Record state
            state_timeline.append({
                'timestamp': ts_str,
                'state': state,
                'delta_t': round(delta_t, 2),
                'ema_delta_t': round(ema_dt, 2),
                'rat': rat,
                'sat': sat,
                'oat': oat,
                'window_open': window_open
            })
            
            last_ema = ema_dt
            last_time = ts
        
        # Filter runs by MIN_ON_SEC
        valid_runs = [r for r in runs if not r.get('ignored', False)]
        
        # Merge runs with short OFF gaps
        merged_runs = self._merge_short_gaps(valid_runs, min_off_sec)
        
        # Calculate aggregates
        total_cycles = len(merged_runs)
        total_runtime = sum(r['duration_sec'] for r in merged_runs)
        avg_cycle_length = total_runtime / total_cycles if total_cycles > 0 else 0
        
        # Calculate window-segmented stats
        cycles_windows_open = sum(1 for r in merged_runs if r.get('window_open'))
        cycles_windows_closed = total_cycles - cycles_windows_open
        
        return {
            'state_timeline': state_timeline,
            'runs': merged_runs,
            'aggregates': {
                'runtime_on_sec': runtime_on_sec,
                'runtime_off_sec': runtime_off_sec,
                'missing_sec': missing_sec,
                'total_cycles': total_cycles,
                'avg_cycle_length_sec': avg_cycle_length,
                'runtime_windows_open_sec': runtime_windows_open,
                'runtime_windows_closed_sec': runtime_windows_closed,
                'cycles_windows_open': cycles_windows_open,
                'cycles_windows_closed': cycles_windows_closed,
                'delta_t_mean': sum(delta_t_values) / len(delta_t_values) if delta_t_values else 0,
                'delta_t_max': max(delta_t_values) if delta_t_values else 0
            },
            'current_state': current_state
        }
    
    def _compute_ema_static(self, current_dt: float, dt_seconds: float, last_ema: float, config: dict) -> float:
        """Static EMA computation"""
        if not config.get('smoothing_enabled', True):
            return current_dt
        
        if last_ema is None:
            return current_dt
        
        tau = config.get('smoothing_tau', 300)
        alpha = 1 - math.exp(-dt_seconds / tau)
        return alpha * current_dt + (1 - alpha) * last_ema
    
    def _merge_short_gaps(self, runs: list, min_off_sec: int) -> list:
        """Merge runs that have short OFF gaps between them"""
        if len(runs) <= 1:
            return runs
        
        merged = [runs[0].copy()]
        
        for run in runs[1:]:
            last_end = datetime.fromisoformat(merged[-1]['end'])
            this_start = datetime.fromisoformat(run['start'])
            gap = (this_start - last_end).total_seconds()
            
            if gap < min_off_sec:
                # Merge with previous run
                merged[-1]['end'] = run['end']
                merged[-1]['duration_sec'] += gap + run['duration_sec']
            else:
                merged.append(run.copy())
        
        return merged
    
    def _get_oat_from_weather(self) -> float:
        """Get outdoor air temperature from the weather API"""
        try:
            # Use the global weather_fetcher which has cached data
            if weather_fetcher and weather_fetcher.cache:
                return weather_fetcher.cache.get('temp')
        except Exception as e:
            logger.warning(f"ACHub: Could not get OAT from weather: {e}")
        return None
    
    def get_current_status(self) -> dict:
        """Get current AC status"""
        # Get latest readings
        samples = self._get_sensor_readings(hours=1)
        
        # Get OAT from weather API
        oat = self._get_oat_from_weather()
        
        if not samples:
            return {
                'state': 'UNKNOWN',
                'message': 'No sensor data available',
                'delta_t': None,
                'ema_delta_t': None,
                'rat': None,
                'sat': None,
                'oat': oat
            }
        
        # Get the latest sample
        latest = samples[-1]
        
        # Compute state from recent history
        result = self.compute_ac_state(samples)
        
        current = result['state_timeline'][-1] if result['state_timeline'] else None
        
        return {
            'state': current['state'] if current else 'UNKNOWN',
            'delta_t': current['delta_t'] if current else None,
            'ema_delta_t': current['ema_delta_t'] if current else None,
            'rat': latest['rat'],
            'sat': latest['sat'],
            'oat': oat,  # Use weather API OAT
            'window_open': latest.get('window_open', False),
            'oat_gating_active': self.config.get('oat_gating_enabled', False),
            'detection_enabled': self._check_oat_gating(oat)
        }
    
    def get_runtime_summary(self, hours: int = 24) -> dict:
        """Get runtime summary for specified time range"""
        samples = self._get_sensor_readings(hours=hours)
        
        if not samples:
            return {
                'runtime_on': '0:00',
                'runtime_on_sec': 0,
                'total_cycles': 0,
                'avg_cycle_length': '0:00',
                'runtime_percent': 0,
                'runtime_windows_open': '0:00',
                'runtime_windows_closed': '0:00'
            }
        
        result = self.compute_ac_state(samples)
        agg = result['aggregates']
        
        # Format times
        def format_duration(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}:{minutes:02d}"
        
        total_time = agg['runtime_on_sec'] + agg['runtime_off_sec']
        runtime_percent = (agg['runtime_on_sec'] / total_time * 100) if total_time > 0 else 0
        
        return {
            'runtime_on': format_duration(agg['runtime_on_sec']),
            'runtime_on_sec': agg['runtime_on_sec'],
            'runtime_off_sec': agg['runtime_off_sec'],
            'total_cycles': agg['total_cycles'],
            'avg_cycle_length': format_duration(agg['avg_cycle_length_sec']),
            'avg_cycle_length_sec': agg['avg_cycle_length_sec'],
            'runtime_percent': round(runtime_percent, 1),
            'runtime_windows_open': format_duration(agg['runtime_windows_open_sec']),
            'runtime_windows_closed': format_duration(agg['runtime_windows_closed_sec']),
            'runtime_windows_open_sec': agg['runtime_windows_open_sec'],
            'runtime_windows_closed_sec': agg['runtime_windows_closed_sec'],
            'cycles_windows_open': agg['cycles_windows_open'],
            'cycles_windows_closed': agg['cycles_windows_closed'],
            'delta_t_mean': round(agg['delta_t_mean'], 1),
            'delta_t_max': round(agg['delta_t_max'], 1),
            'missing_sec': agg['missing_sec']
        }
    
    def get_available_sensors(self) -> list:
        """Get list of available sensors from HomeHub (temp sensors and contact sensors)"""
        sensors = []
        try:
            for device_id, device in homehub_manager.devices.items():
                device_type = device.get('type', '')
                friendly_name = device.get('friendly_name', device_id)
                
                # Include sensors (temperature) and contact sensors
                if device_type in ('sensor', 'contact'):
                    # Check current state to determine capabilities
                    state = homehub_manager.device_states.get(friendly_name, {})
                    
                    # Use device type as fallback for capabilities
                    # Contact sensors may not report contact until state changes
                    has_temperature = state.get('temperature') is not None or device_type == 'sensor'
                    has_contact = state.get('contact') is not None or device_type == 'contact'
                    
                    # Also check database for capabilities if state is empty
                    if not state:
                        db_device = homehub_manager.get_devices()
                        for d in db_device:
                            if d.get('friendly_name') == friendly_name:
                                db_state = d.get('state', {})
                                has_temperature = has_temperature or db_state.get('temperature') is not None
                                has_contact = has_contact or db_state.get('contact') is not None
                                break
                    
                    sensors.append({
                        'id': device_id,
                        'name': friendly_name,
                        'model': device.get('model', 'Unknown'),
                        'type': device_type,
                        'has_temperature': has_temperature,
                        'has_contact': has_contact
                    })
        except Exception as e:
            logger.warning(f"ACHub: Could not get sensors: {e}")
        return sensors
    
    def get_budget_estimate(self, hours: int = 24) -> dict:
        """Calculate cost/budget estimates with peak pricing support"""
        # Get detailed state timeline to calculate peak vs off-peak
        samples = self._get_sensor_readings(hours=hours)
        
        ac_kw = self.config.get('ac_kw_running', 3.5)
        rate_normal = self.config.get('rate_per_kwh', 0.12)
        rate_peak = self.config.get('peak_rate_per_kwh', 0.25)
        peak_start = self.config.get('peak_start_hour', 14)
        peak_end = self.config.get('peak_end_hour', 19)
        peak_enabled = self.config.get('peak_enabled', False)
        exclude_windows = self.config.get('exclude_windows_open', False)
        
        # If no samples, return zeros
        if not samples:
            return {
                'runtime_hours': 0,
                'kwh_estimated': 0,
                'cost_estimated': 0,
                'runtime_hours_effective': 0,
                'kwh_effective': 0,
                'cost_effective': 0,
                'peak_runtime_hours': 0,
                'peak_kwh': 0,
                'peak_cost': 0,
                'offpeak_runtime_hours': 0,
                'offpeak_kwh': 0,
                'offpeak_cost': 0,
                'ac_kw_setting': ac_kw,
                'rate_per_kwh': rate_normal,
                'peak_rate_per_kwh': rate_peak,
                'peak_start_hour': peak_start,
                'peak_end_hour': peak_end,
                'peak_enabled': peak_enabled,
                'exclude_windows_open': exclude_windows
            }
        
        result = self.compute_ac_state(samples)
        timeline = result['state_timeline']
        
        # Calculate runtime split by peak/off-peak
        runtime_peak_sec = 0
        runtime_offpeak_sec = 0
        last_time = None
        
        for entry in timeline:
            ts_str = entry['timestamp']
            state = entry['state']
            window_open = entry.get('window_open', False)
            
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            
            if last_time is not None and state == 'ON':
                # Skip if excluding windows open time
                if exclude_windows and window_open:
                    last_time = ts
                    continue
                    
                dt_sec = (ts - last_time).total_seconds()
                if dt_sec > 0 and dt_sec < 3600:  # Cap at 1 hour to avoid bad data
                    hour = ts.hour
                    # Check if in peak hours
                    if peak_start <= hour < peak_end:
                        runtime_peak_sec += dt_sec
                    else:
                        runtime_offpeak_sec += dt_sec
            
            last_time = ts
        
        # Calculate costs
        runtime_peak_hours = runtime_peak_sec / 3600
        runtime_offpeak_hours = runtime_offpeak_sec / 3600
        runtime_total_hours = runtime_peak_hours + runtime_offpeak_hours
        
        kwh_peak = runtime_peak_hours * ac_kw
        kwh_offpeak = runtime_offpeak_hours * ac_kw
        kwh_total = kwh_peak + kwh_offpeak
        
        if peak_enabled:
            cost_peak = kwh_peak * rate_peak
            cost_offpeak = kwh_offpeak * rate_normal
            cost_total = cost_peak + cost_offpeak
        else:
            cost_peak = kwh_peak * rate_normal
            cost_offpeak = kwh_offpeak * rate_normal
            cost_total = kwh_total * rate_normal
        
        return {
            'runtime_hours': round(runtime_total_hours, 2),
            'kwh_estimated': round(kwh_total, 2),
            'cost_estimated': round(cost_total, 2),
            'runtime_hours_effective': round(runtime_total_hours, 2),
            'kwh_effective': round(kwh_total, 2),
            'cost_effective': round(cost_total, 2),
            'peak_runtime_hours': round(runtime_peak_hours, 2),
            'peak_kwh': round(kwh_peak, 2),
            'peak_cost': round(cost_peak, 2),
            'offpeak_runtime_hours': round(runtime_offpeak_hours, 2),
            'offpeak_kwh': round(kwh_offpeak, 2),
            'offpeak_cost': round(cost_offpeak, 2),
            'ac_kw_setting': ac_kw,
            'rate_per_kwh': rate_normal,
            'peak_rate_per_kwh': rate_peak,
            'peak_start_hour': peak_start,
            'peak_end_hour': peak_end,
            'peak_enabled': peak_enabled,
            'exclude_windows_open': exclude_windows
        }
    
    def get_chart_data(self, hours: int = 24) -> dict:
        """Get data formatted for charts"""
        samples = self._get_sensor_readings(hours=hours)
        
        if not samples:
            return {'timestamps': [], 'rat': [], 'sat': [], 'oat': [], 'delta_t': [], 'ema_delta_t': [], 'state': []}
        
        result = self.compute_ac_state(samples)
        timeline = result['state_timeline']
        
        return {
            'timestamps': [s['timestamp'] for s in timeline],
            'rat': [s['rat'] for s in timeline],
            'sat': [s['sat'] for s in timeline],
            'oat': [s['oat'] for s in timeline],
            'delta_t': [s['delta_t'] for s in timeline],
            'ema_delta_t': [s['ema_delta_t'] for s in timeline],
            'state': [s['state'] for s in timeline],
            'window_open': [s['window_open'] for s in timeline]
        }
    
    # =========================================================================
    # SERVER WATTS → COOLING COST COMPUTATION
    # =========================================================================
    
    def submit_server_watts(self, watts: float, source: str = 'manual') -> dict:
        """Store a server watts reading"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO server_watts (watts, source) VALUES (?, ?)',
                (watts, source)
            )
            conn.commit()
            conn.close()
            return {'success': True, 'watts': watts}
        except Exception as e:
            logger.error(f"ACHub: Failed to store server watts: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_server_watts_history(self, hours: int = 24) -> list:
        """Get server watts time series"""
        import sqlite3
        readings = []
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            since = datetime.now() - timedelta(hours=hours)
            cursor.execute('''
                SELECT timestamp, watts, source FROM server_watts
                WHERE timestamp >= ? ORDER BY timestamp ASC
            ''', (since.strftime('%Y-%m-%d %H:%M:%S'),))
            
            for row in cursor.fetchall():
                readings.append({
                    'timestamp': row['timestamp'],
                    'watts': row['watts'],
                    'source': row['source']
                })
            
            conn.close()
        except Exception as e:
            logger.error(f"ACHub: Failed to get server watts: {e}")
        
        return readings
    
    def compute_electrical_kw_for_heat(self, heat_kw: float) -> float:
        """
        Convert heat load (kW) to electrical kW using the configured efficiency model.
        Returns None if efficiency model is not configured.
        """
        mode = self.config.get('efficiency_mode')
        
        if mode == 'COP':
            cop = self.config.get('cop_value')
            if cop and cop > 0:
                return heat_kw / cop
        elif mode == 'EER':
            eer = self.config.get('eer_value')
            if eer and eer > 0:
                # EER is BTU/hr per watt
                # heat_kw * 1000 * 3.412 = BTU/hr
                # electrical_W = BTU_hr / EER
                heat_btu_hr = heat_kw * 1000 * 3.412
                electrical_w = heat_btu_hr / eer
                return electrical_w / 1000
        elif mode == 'MULTIPLIER':
            mult = self.config.get('kw_per_kw_heat')
            if mult and mult > 0:
                return heat_kw * mult
        
        return None
    
    def compute_server_cost(self, server_samples: list, sat_value: float = None,
                           window_open_status: bool = False, config: dict = None) -> dict:
        """
        Compute server cooling cost from server watts time series.
        
        Uses SAT gating: cost only accrues when SAT <= threshold (default 65°F).
        SAT <= 65°F indicates AC compressor is actively running and cooling.
        
        Args:
            server_samples: List of {timestamp, watts}
            sat_value: Current supply air temperature (°F)
            window_open_status: Whether windows are currently open
            config: Optional override config
        
        Returns:
            Dict with timeseries and aggregates
        """
        if config is None:
            config = self.config
        
        # Check if efficiency model is configured
        mode = config.get('efficiency_mode')
        rate_per_kwh = config.get('rate_per_kwh', 0.12)
        peak_rate = config.get('peak_rate_per_kwh', 0.25)
        peak_enabled = config.get('peak_enabled', False)
        peak_start = config.get('peak_start_hour', 14)
        peak_end = config.get('peak_end_hour', 19)
        max_gap_sec = config.get('server_max_gap_sec', 900)
        gating_mode = config.get('server_gating_mode', 'BOTH')
        exclude_windows = config.get('server_exclude_windows_open', False)
        sat_threshold = config.get('server_sat_gating_threshold', 65.0)
        
        # Determine if AC is running (SAT <= threshold means AC compressor is on)
        ac_is_running = sat_value is not None and sat_value <= sat_threshold
        
        # Results
        cost_timeline = []
        last_time = None
        
        # Aggregates
        total_thermo_cost = 0.0
        total_ac_gated_cost = 0.0  # Cost when AC is running (SAT <= threshold)
        total_thermo_cost_windows_closed = 0.0
        total_thermo_cost_windows_open = 0.0
        total_ac_gated_cost_windows_closed = 0.0
        total_ac_gated_cost_windows_open = 0.0
        total_server_kwh = 0.0
        total_samples = 0
        sum_watts = 0.0
        
        for sample in server_samples:
            ts_str = sample['timestamp']
            watts = sample.get('watts', 0)
            
            if watts is None or watts < 0:
                continue
            
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                try:
                    ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                except:
                    continue
            
            # Compute heat and electrical equivalents
            heat_kw = watts / 1000.0
            heat_btu_hr = watts * 3.412
            electrical_kw = self.compute_electrical_kw_for_heat(heat_kw)
            
            # Use window status passed in (from Zigbee sensor)
            window_open = window_open_status
            
            # Compute cost rates
            hour = ts.hour
            current_rate = peak_rate if (peak_enabled and peak_start <= hour < peak_end) else rate_per_kwh
            
            cost_rate_per_hr = (electrical_kw * current_rate) if electrical_kw else None
            # AC gated cost: only when SAT <= threshold (AC is running)
            cost_rate_ac_gated = (electrical_kw * current_rate) if (electrical_kw and ac_is_running) else 0.0
            
            # Integrate cost over time
            if last_time is not None:
                dt_sec = (ts - last_time).total_seconds()
                
                # Only integrate if gap is acceptable
                if 0 < dt_sec <= max_gap_sec:
                    dt_hours = dt_sec / 3600.0
                    
                    # Server kWh accumulation
                    total_server_kwh += (watts / 1000.0) * dt_hours
                    
                    if electrical_kw is not None:
                        # Thermodynamic equivalent cost (always)
                        interval_thermo = electrical_kw * dt_hours * current_rate
                        total_thermo_cost += interval_thermo
                        
                        if window_open:
                            total_thermo_cost_windows_open += interval_thermo
                        else:
                            total_thermo_cost_windows_closed += interval_thermo
                        
                        # AC-gated cost (only when SAT <= threshold)
                        if ac_is_running:
                            interval_gated = electrical_kw * dt_hours * current_rate
                            total_ac_gated_cost += interval_gated
                            
                            if window_open:
                                total_ac_gated_cost_windows_open += interval_gated
                            else:
                                total_ac_gated_cost_windows_closed += interval_gated
            
            total_samples += 1
            sum_watts += watts
            last_time = ts
            
            # Add to timeline
            cost_timeline.append({
                'timestamp': ts_str,
                'server_watts': watts,
                'heat_btu_hr': round(heat_btu_hr, 1),
                'heat_kw': round(heat_kw, 3),
                'electrical_kw': round(electrical_kw, 3) if electrical_kw else None,
                'cost_rate_per_hr': round(cost_rate_per_hr, 4) if cost_rate_per_hr else None,
                'cost_rate_ac_gated': round(cost_rate_ac_gated, 4) if cost_rate_ac_gated else 0.0,
                'ac_is_running': ac_is_running,
                'sat_value': sat_value,
                'window_open': window_open
            })
        
        # Compute averages
        avg_watts = (sum_watts / total_samples) if total_samples > 0 else 0
        
        # Effective costs (optionally excluding windows open)
        effective_thermo_cost = total_thermo_cost_windows_closed if exclude_windows else total_thermo_cost
        effective_ac_gated_cost = total_ac_gated_cost_windows_closed if exclude_windows else total_ac_gated_cost
        
        return {
            'cost_timeline': cost_timeline,
            'aggregates': {
                'total_samples': total_samples,
                'avg_server_watts': round(avg_watts, 1),
                'total_server_kwh': round(total_server_kwh, 2),
                
                # Thermodynamic equivalent (if AC ran continuously)
                'thermo_cost_total': round(total_thermo_cost, 4),
                'thermo_cost_windows_closed': round(total_thermo_cost_windows_closed, 4),
                'thermo_cost_windows_open': round(total_thermo_cost_windows_open, 4),
                
                # AC-gated cost (when SAT <= threshold, AC is running)
                'ac_active_cost_total': round(total_ac_gated_cost, 4),
                'ac_active_cost_windows_closed': round(total_ac_gated_cost_windows_closed, 4),
                'ac_active_cost_windows_open': round(total_ac_gated_cost_windows_open, 4),
                
                # Effective costs (with exclusion applied)
                'effective_thermo_cost': round(effective_thermo_cost, 4),
                'effective_ac_active_cost': round(effective_ac_gated_cost, 4),
                
                # Config used
                'efficiency_mode': mode,
                'rate_per_kwh': rate_per_kwh,
                'peak_rate_per_kwh': peak_rate if peak_enabled else None,
                'exclude_windows_open': exclude_windows,
                'sat_gating_threshold': sat_threshold,
                'ac_is_running': ac_is_running,
                'sat_value': sat_value
            }
        }
    
    def _get_current_sat(self) -> float:
        """Get current SAT (Supply Air Temperature) from temp history"""
        import sqlite3
        sat_sensor = self.config.get('sat_sensor', 'AC Supply Temp')
        logger.debug(f"ACHub: Looking for SAT sensor: {sat_sensor}")
        try:
            conn = sqlite3.connect('/home/admin/wallclock/temp_history.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get most recent reading for SAT sensor
            cursor.execute('''
                SELECT temperature FROM temp_readings 
                WHERE friendly_name = ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (sat_sensor,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row['temperature'] is not None:
                temp_f = self._celsius_to_fahrenheit(row['temperature'])
                logger.debug(f"ACHub: Got SAT {row['temperature']}°C = {temp_f}°F")
                return temp_f
            else:
                logger.debug(f"ACHub: No SAT reading found for {sat_sensor}")
        except Exception as e:
            logger.warning(f"ACHub: Could not get SAT: {e}")
        return None
    
    def _get_window_open_status(self, sensor_name: str = None) -> bool:
        """
        Get window open status from Zigbee contact sensor.
        
        Args:
            sensor_name: Optional specific sensor name. If None, uses configured sensor.
        
        Returns:
            True if window is open, False if closed or no sensor configured.
        """
        window_sensor = sensor_name or self.config.get('server_window_sensor')
        if not window_sensor:
            return False
        try:
            # Check device_states cache first (most up-to-date)
            state = homehub_manager.device_states.get(window_sensor, {})
            contact = state.get('contact')
            if contact is not None:
                return not contact  # contact=False means window is open
            
            # Fallback to database if no cached state
            latest = homehub_manager.get_latest_contact_reading(window_sensor)
            if latest and latest.get('contact') is not None:
                return not latest['contact']
                
        except Exception as e:
            logger.warning(f"ACHub: Could not get window status for {window_sensor}: {e}")
        return False
    
    def get_server_cost_status(self) -> dict:
        """Get current server load and cost status (latest values)"""
        # Get latest server watts
        readings = self.get_server_watts_history(hours=1)
        
        # Get current SAT for gating
        sat_value = self._get_current_sat()
        sat_threshold = self.config.get('server_sat_gating_threshold', 65.0)
        ac_is_running = sat_value is not None and sat_value <= sat_threshold
        
        # Get window status
        window_open = self._get_window_open_status()
        
        if not readings:
            return {
                'has_data': False,
                'efficiency_configured': self.config.get('efficiency_mode') is not None,
                'server_watts_now': None,
                'heat_btu_hr_now': None,
                'heat_kw_now': None,
                'electrical_kw_now': None,
                'cost_rate_per_hr_now': None,
                'cost_rate_ac_gated_now': None,
                'ac_is_running': ac_is_running,
                'sat_value': sat_value,
                'sat_threshold': sat_threshold,
                'window_open': window_open
            }
        
        # Get latest reading
        latest = readings[-1]
        watts = latest['watts']
        heat_kw = watts / 1000.0
        heat_btu_hr = watts * 3.412
        electrical_kw = self.compute_electrical_kw_for_heat(heat_kw)
        
        # Compute cost rate
        rate_per_kwh = self.config.get('rate_per_kwh', 0.12)
        peak_rate = self.config.get('peak_rate_per_kwh', 0.25)
        peak_enabled = self.config.get('peak_enabled', False)
        peak_start = self.config.get('peak_start_hour', 14)
        peak_end = self.config.get('peak_end_hour', 19)
        
        hour = datetime.now().hour
        current_rate = peak_rate if (peak_enabled and peak_start <= hour < peak_end) else rate_per_kwh
        
        cost_rate = (electrical_kw * current_rate) if electrical_kw else None
        # AC gated: cost only when SAT <= threshold (AC is running)
        cost_rate_ac_gated = cost_rate if (electrical_kw and ac_is_running) else 0.0
        
        return {
            'has_data': True,
            'efficiency_configured': self.config.get('efficiency_mode') is not None,
            'timestamp': latest['timestamp'],
            'server_watts_now': round(watts, 1),
            'heat_btu_hr_now': round(heat_btu_hr, 1),
            'heat_kw_now': round(heat_kw, 3),
            'electrical_kw_now': round(electrical_kw, 3) if electrical_kw else None,
            'cost_rate_per_hr_now': round(cost_rate, 4) if cost_rate else None,
            'cost_rate_ac_gated_now': round(cost_rate_ac_gated, 4),
            'ac_is_running': ac_is_running,
            'sat_value': round(sat_value, 1) if sat_value else None,
            'sat_threshold': sat_threshold,
            'window_open': window_open,
            'is_peak_hour': peak_enabled and peak_start <= hour < peak_end
        }
    
    def get_server_cost_summary(self, hours: int = 24) -> dict:
        """Get aggregated server cooling cost for a time period"""
        # Get server watts
        server_samples = self.get_server_watts_history(hours=hours)
        
        # Get current SAT and window status for gating
        sat_value = self._get_current_sat()
        window_open = self._get_window_open_status()
        
        if not server_samples:
            return {
                'has_data': False,
                'hours': hours,
                'efficiency_configured': self.config.get('efficiency_mode') is not None,
                'aggregates': None
            }
        
        # Compute costs with SAT gating
        result = self.compute_server_cost(server_samples, sat_value, window_open)
        
        return {
            'has_data': True,
            'hours': hours,
            'efficiency_configured': self.config.get('efficiency_mode') is not None,
            'aggregates': result['aggregates']
        }
    
    def get_server_chart_data(self, hours: int = 24) -> dict:
        """Get server watts and cost data formatted for charts"""
        # Get server watts
        server_samples = self.get_server_watts_history(hours=hours)
        
        # Get current SAT and window status
        sat_value = self._get_current_sat()
        window_open = self._get_window_open_status()
        
        if not server_samples:
            return {
                'timestamps': [],
                'server_watts': [],
                'heat_kw': [],
                'electrical_kw': [],
                'cost_rate_per_hr': [],
                'cost_rate_ac_gated': [],
                'ac_is_running': []
            }
        
        # Compute costs with SAT gating
        result = self.compute_server_cost(server_samples, sat_value, window_open)
        timeline = result['cost_timeline']
        
        return {
            'timestamps': [s['timestamp'] for s in timeline],
            'server_watts': [s['server_watts'] for s in timeline],
            'heat_kw': [s['heat_kw'] for s in timeline],
            'electrical_kw': [s['electrical_kw'] for s in timeline],
            'cost_rate_per_hr': [s['cost_rate_per_hr'] for s in timeline],
            'cost_rate_ac_gated': [s['cost_rate_ac_gated'] for s in timeline],
            'ac_is_running': [s['ac_is_running'] for s in timeline],
            'window_open': [s['window_open'] for s in timeline]
        }


# Global AC Hub manager instance
achub_manager = ACHubManager()


# AC Hub Routes
@app.get("/achub")
async def achub_page():
    """Serve AC Hub dashboard"""
    return FileResponse("frontend/achub.html")


@app.get("/api/achub/status")
async def achub_status():
    """Get current AC status"""
    return achub_manager.get_current_status()


@app.get("/api/achub/config")
async def achub_get_config():
    """Get AC Hub configuration"""
    return achub_manager.get_config()


@app.post("/api/achub/config")
async def achub_update_config(request: Request):
    """Update AC Hub configuration"""
    data = await request.json()
    achub_manager.update_config(data)
    return {'success': True, 'config': achub_manager.get_config()}


@app.get("/api/achub/sensors")
async def achub_get_sensors():
    """Get available temperature sensors from HomeHub"""
    return {'sensors': achub_manager.get_available_sensors()}


@app.get("/api/achub/runtime")
async def achub_runtime(hours: int = 24):
    """Get runtime summary"""
    return achub_manager.get_runtime_summary(hours)


@app.get("/api/achub/budget")
async def achub_budget(hours: int = 24):
    """Get budget/cost estimates"""
    return achub_manager.get_budget_estimate(hours)


@app.get("/api/achub/chart-data")
async def achub_chart_data(hours: int = 24):
    """Get chart data for visualization"""
    return achub_manager.get_chart_data(hours)


@app.get("/api/achub/history")
async def achub_history(hours: int = 24):
    """Get detailed history with state timeline"""
    samples = achub_manager._get_sensor_readings(hours=hours)
    return achub_manager.compute_ac_state(samples)


# Server Watts → Cooling Cost Endpoints
@app.post("/api/achub/server-watts")
async def submit_server_watts(request: Request):
    """Submit a server watts reading"""
    data = await request.json()
    watts = data.get('watts')
    source = data.get('source', 'manual')
    
    if watts is None:
        return {'success': False, 'error': 'watts is required'}
    
    return achub_manager.submit_server_watts(float(watts), source)


@app.get("/api/achub/server-watts")
async def get_server_watts(hours: int = 24):
    """Get server watts history"""
    return {'readings': achub_manager.get_server_watts_history(hours)}


@app.get("/api/achub/server-cost/status")
async def server_cost_status():
    """Get current server load and cost status"""
    return achub_manager.get_server_cost_status()


@app.get("/api/achub/server-cost/summary")
async def server_cost_summary(hours: int = 24):
    """Get aggregated server cooling cost for a time period"""
    return achub_manager.get_server_cost_summary(hours)


@app.get("/api/achub/server-cost/chart-data")
async def server_cost_chart_data(hours: int = 24):
    """Get server cost data formatted for charts"""
    return achub_manager.get_server_chart_data(hours)


# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize data on startup"""
    global weather_fetcher, calendar_fetcher
    
    logger.info("="*50)
    logger.info("Wall Clock API Server Starting")
    logger.info("="*50)
    
    # Load saved config from file
    load_config_from_file()
    
    # Reinitialize fetchers with loaded config
    weather_fetcher = WeatherFetcher()
    calendar_fetcher = CalendarFetcher()

    # Pre-fetch data
    await weather_fetcher.fetch_weather()
    await calendar_fetcher.fetch_events()
    await note_fetcher.fetch_note()

    logger.info("Initial data fetched successfully")
    
    # Initialize Home Hub (Zigbee2MQTT connection)
    logger.info("Initializing Home Hub...")
    try:
        await homehub_manager.connect_mqtt()
        if homehub_manager.connected:
            logger.info("Home Hub: Connected to Zigbee2MQTT")
            # Start temperature logging
            await homehub_manager.start_temp_logging()
            logger.info("Home Hub: Temperature logging started")
        else:
            logger.info("Home Hub: Not connected (Zigbee2MQTT may not be running)")
    except Exception as e:
        logger.warning(f"Home Hub: Could not connect: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
