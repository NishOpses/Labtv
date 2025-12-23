#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import io
import platform
import qrcode
import psutil
import threading
import time
import subprocess
import requests
import json
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template_string, send_file, request, jsonify, send_from_directory

# Weather caching logic
WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")
WEATHER_API_KEY = "144536c74a836feb69c1cd449b8457b9"
WEATHER_LAT = 51.0902
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15  # 96 calls/day max

def get_weather():
    now = datetime.utcnow()
    # Try cache
    if os.path.exists(WEATHER_CACHE_FILE):
        try:
            with open(WEATHER_CACHE_FILE, "r") as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data.get("timestamp"))
            if (now - ts) < timedelta(minutes=WEATHER_CACHE_MINUTES):
                print("[DEBUG] Using cached weather data")
                return data["weather"]
        except Exception as e:
            print(f"[DEBUG] Error reading weather cache: {e}")
    # Fetch from API
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={WEATHER_LAT}&lon={WEATHER_LON}&appid={WEATHER_API_KEY}&units=metric"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            w = resp.json()
            weather = {
                "temp": int(round(w["main"]["temp"])),
                "desc": w["weather"][0]["description"].title(),
                "icon_url": f"https://openweathermap.org/img/wn/{w['weather'][0]['icon']}@4x.png"
            }
            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "weather": weather}, f)
            print("[DEBUG] Weather fetched and cached")
            return weather
        else:
            print(f"[DEBUG] Weather API failed with status {resp.status_code}")
    except Exception as e:
        print(f"[DEBUG] Exception fetching weather: {e}")
    return None
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import io
import platform
import qrcode
import psutil
import threading
import time
import subprocess
import requests
import json
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template_string, send_file, request, jsonify, send_from_directory

# Try to import required modules with fallbacks
try:
    from useful_info import get_time_info
except ImportError:
    print("[WARNING] useful_info module not found. Using fallback date function.")
    def get_time_info():
        return {"date": datetime.now().strftime("%A, %d %B %Y")}

try:
    from ics import Calendar
    ics_available = True
except ImportError:
    print("[WARNING] ics module not available. Calendar functionality disabled.")
    ics_available = False

# =====================
# Network Scanner Integration
# =====================
try:
    from network_scanner import NetworkScanner
    NETWORK_SCANNER_AVAILABLE = True
    print("[DEBUG] Network scanner module loaded successfully")
    network_scanner = NetworkScanner()
except ImportError as e:
    print(f"[WARNING] Network scanner module not available: {e}")
    print("[WARNING] Falling back to basic ARP table detection")
    NETWORK_SCANNER_AVAILABLE = False

# Fallback functions
def get_present_absent_colleagues_fallback():
    """Fallback function using old ARP table method"""
    try:
        colleagues_file = os.path.join(os.path.dirname(__file__), "colleagues.json")
        if not os.path.exists(colleagues_file):
            print("[DEBUG] Colleagues file not found")
            return [], []
        
        with open(colleagues_file, "r", encoding="utf-8") as f:
            colleagues = json.load(f)
        
        # Get ARP table
        if platform.system().lower() == "windows":
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        else:
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        
        present = []
        absent = []
        
        for name, mac in colleagues.items():
            if mac and mac.lower() in output.lower():
                present.append(name)
            else:
                absent.append(name)
                
        print(f"[DEBUG] Fallback: Present: {len(present)}, Absent: {len(absent)}")
        return present, absent
        
    except Exception as e:
        print(f"[DEBUG] Fallback detection error: {e}")
        return [], []

def get_present_absent_colleagues():
    """Get presence using new scanner or fallback"""
    if NETWORK_SCANNER_AVAILABLE:
        try:
            present, absent = network_scanner.detect_presence()
            print(f"[DEBUG] Scanner: Present: {len(present)}, Absent: {len(absent)}")
            return present, absent
        except Exception as e:
            print(f"[ERROR] Scanner failed: {e}")
            return get_present_absent_colleagues_fallback()
    else:
        return get_present_absent_colleagues_fallback()

# =====================
# Calendar Feed Config
# =====================
OUTLOOK_ICAL_URL = os.environ.get("OUTLOOK_ICAL_URL", "https://outlook.office365.com/owa/calendar/744e18cdc1534f5dbcdf3283c76a8f8b@opses.co.uk/85260d62ab584bd69aca5ac9a4223dd84268036899588616720/calendar.ics")
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

def get_calendar_events():
    if not ics_available:
        print("[DEBUG] ICS module not available, returning empty calendar events")
        return []
    
    print("[DEBUG] get_calendar_events: Called")
    if not OUTLOOK_ICAL_URL or OUTLOOK_ICAL_URL == "":
        print("[DEBUG] No OUTLOOK_ICAL_URL set")
        return []
    
    try:
        import pytz
        utc = pytz.UTC
        now = datetime.utcnow().replace(tzinfo=utc)
        
        # Try cache
        if os.path.exists(CALENDAR_CACHE_FILE):
            try:
                with open(CALENDAR_CACHE_FILE, "r") as f:
                    data = json.load(f)
                ts = datetime.fromisoformat(data.get("timestamp"))
                if (now - ts) < timedelta(minutes=CALENDAR_CACHE_MINUTES):
                    print(f"[DEBUG] Using cached calendar events: {len(data['events'])} events")
                    return data["events"]
            except Exception as e:
                print(f"[DEBUG] Error reading calendar cache: {e}")
        
        # Fetch from iCal feed
        print(f"[DEBUG] Fetching ICS feed: {OUTLOOK_ICAL_URL}")
        resp = requests.get(OUTLOOK_ICAL_URL, timeout=10)
        print(f"[DEBUG] ICS HTTP status: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                c = Calendar(resp.text)
                events = []
                for e in sorted(c.timeline, key=lambda ev: ev.begin):
                    # Ensure event datetime is offset-aware (UTC)
                    event_start = e.begin.datetime
                    if event_start.tzinfo is None:
                        event_start = event_start.replace(tzinfo=utc)
                    else:
                        event_start = event_start.astimezone(utc)

                    # Handle event end (may be None for single-point events)
                    event_end = getattr(e, 'end', None)
                    if event_end:
                        event_end = event_end.datetime
                        if event_end.tzinfo is None:
                            event_end = event_end.replace(tzinfo=utc)
                        else:
                            event_end = event_end.astimezone(utc)
                    else:
                        event_end = event_start

                    # Show events that are:
                    # - currently in progress (now between start and end)
                    # - or upcoming (start >= now)
                    # - and within the next 7 days
                    if (
                        (event_start <= now <= event_end) or
                        (event_start >= now)
                    ) and event_start <= now + timedelta(days=7):
                        events.append({
                            "start": event_start.strftime('%Y-%m-%d %H:%M'),
                            "summary": e.name or "(No Title)",
                            "location": getattr(e, 'location', None) or ""
                        })
                        if len(events) >= 5:
                            break
                
                print(f"[DEBUG] Parsed {len(events)} upcoming events from ICS feed")
                
                # Save to cache
                try:
                    with open(CALENDAR_CACHE_FILE, "w") as f:
                        json.dump({"timestamp": now.isoformat(), "events": events}, f)
                except Exception as e:
                    print(f"[DEBUG] Error saving calendar cache: {e}")
                
                return events
            except Exception as e:
                print(f"[DEBUG] Error parsing ICS feed: {e}")
                return []
        else:
            print(f"[DEBUG] ICS feed fetch failed with status {resp.status_code}")
            return []
    except Exception as e:
        print(f"[DEBUG] Exception fetching/parsing ICS feed: {e}")
        return []
    
    return []

# =====================
# App setup
# =====================
app = Flask(__name__)

WIFI_SSID = os.environ.get("WIFI_SSID", "Opses_Global_Guest")
WIFI_PASSWORD = os.environ.get("WIFI_PASSWORD", "Covert3791Beer105%")
WIFI_AUTH = os.environ.get("WIFI_AUTH", "WPA")

# =====================
# Background updater
# =====================
UPDATE_CHECK_INTERVAL = 3600
UPDATE_COMMAND = os.environ.get("KIOSK_UPDATE_COMMAND", "git pull")
LAST_UPDATE_FILE = os.path.join(os.path.dirname(__file__), "last_update.txt")

def background_update_loop():
    while True:
        try:
            print("[DEBUG] Running background update check...")
            result = subprocess.run(
                UPDATE_COMMAND,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            with open(LAST_UPDATE_FILE, "w") as f:
                f.write(f"Last checked: {datetime.now().isoformat()}\n")
                f.write(f"Command: {UPDATE_COMMAND}\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"Output:\n{result.stdout}\nErrors:\n{result.stderr}\n")
            print(f"[DEBUG] Update check completed. Return code: {result.returncode}")
        except Exception as e:
            print(f"[DEBUG] Update error: {e}")
            try:
                with open(LAST_UPDATE_FILE, "a") as f:
                    f.write(f"Update error at {datetime.now().isoformat()}: {e}\n")
            except:
                pass
        time.sleep(UPDATE_CHECK_INTERVAL)

# =====================
# Optimized HTML Template for Portrait 1080x1920
# =====================
TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Opses Lab Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #0a0e14 0%, #1a1f29 100%);
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-x: hidden;
            position: relative;
        }
        
        /* Main content container - optimized for vertical flow */
        .main-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            max-width: 1000px;
            padding: 2vh 3vw;
            gap: 3vh;
            margin-top: 1vh;
            overflow-y: auto;
            height: 100vh;
        }
        
        /* Header section */
        .header-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            margin-bottom: 1vh;
        }
        
        .company-logo {
            width: 25vw;
            max-width: 250px;
            min-width: 150px;
            background: #fff;
            border-radius: 20px;
            padding: 8px;
            margin-bottom: 2vh;
            box-shadow: 0 6px 30px rgba(0,0,0,0.4);
        }
        
        /* Time section - larger and centered */
        .time-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 4vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            width: 90%;
            max-width: 900px;
            margin-bottom: 1vh;
            backdrop-filter: blur(10px);
        }
        
        .public-clock {
            font-size: 15vw;
            color: #fff;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-shadow: 0 4px 20px rgba(0,0,0,0.7);
            font-family: 'Courier New', monospace;
            line-height: 1;
            margin: 1vh 0;
        }
        
        .clock-colon {
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .public-date {
            font-size: 4vw;
            color: #b0b7c3;
            font-weight: 500;
            text-align: center;
            margin-top: 1vh;
            letter-spacing: 0.05em;
        }
        
        /* Info panels - side by side on portrait */
        .info-panels {
            display: flex;
            flex-direction: row;
            justify-content: space-between;
            width: 100%;
            max-width: 950px;
            gap: 2vw;
            margin: 1vh 0;
        }
        
        .panel {
            flex: 1;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 2.5vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
            min-height: 200px;
            display: flex;
            flex-direction: column;
        }
        
        .panel-title {
            font-size: 3.5vw;
            color: #2ecc40;
            font-weight: 700;
            margin-bottom: 1.5vh;
            text-align: center;
            border-bottom: 2px solid #2ecc40;
            padding-bottom: 0.5vh;
        }
        
        /* Weather panel */
        .weather-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-grow: 1;
        }
        
        .weather-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 3vw;
            margin-bottom: 1vh;
        }
        
        .weather-icon {
            width: 15vw;
            max-width: 120px;
            min-width: 80px;
        }
        
        .weather-temp {
            font-size: 10vw;
            color: #2ecc40;
            font-weight: 800;
            text-shadow: 0 2px 10px rgba(46, 204, 64, 0.3);
        }
        
        .weather-desc {
            font-size: 3vw;
            color: #b0b7c3;
            text-align: center;
            margin-top: 0.5vh;
        }
        
        /* Calendar panel */
        .calendar-content {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }
        
        .calendar-events-list {
            list-style: none;
            padding: 0;
            margin: 0;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 30vh;
        }
        
        .calendar-events-list::-webkit-scrollbar {
            width: 6px;
        }
        
        .calendar-events-list::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }
        
        .calendar-events-list::-webkit-scrollbar-thumb {
            background: #2ecc40;
            border-radius: 3px;
        }
        
        .calendar-events-list li {
            padding: 1.5vh 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .event-date {
            color: #2ecc40;
            font-weight: 700;
            font-size: 2.5vw;
            display: block;
            margin-bottom: 0.3vh;
        }
        
        .event-summary {
            color: #fff;
            font-size: 2.8vw;
            display: block;
            margin-bottom: 0.3vh;
        }
        
        .event-location {
            color: #b0b7c3;
            font-size: 2.2vw;
            display: block;
            font-style: italic;
        }
        
        .no-events {
            color: #888;
            font-size: 3vw;
            text-align: center;
            padding: 3vh 0;
            font-style: italic;
        }
        
        /* Presence panel - moved to main flow */
        .presence-panel {
            width: 90%;
            max-width: 900px;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 3vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            margin: 1vh 0 3vh 0;
            backdrop-filter: blur(10px);
        }
        
        .presence-content {
            display: flex;
            flex-direction: row;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 2vw;
            margin-top: 1vh;
        }
        
        .presence-column {
            flex: 1;
            min-width: 200px;
        }
        
        .presence-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .presence-list li {
            padding: 0.8vh 0;
            font-size: 2.8vw;
            display: flex;
            align-items: center;
        }
        
        .present-badge {
            display: inline-block;
            width: 2.5vw;
            height: 2.5vw;
            min-width: 12px;
            min-height: 12px;
            background-color: #2ecc40;
            border-radius: 50%;
            margin-right: 1.5vw;
            box-shadow: 0 0 8px #2ecc40;
        }
        
        .absent-badge {
            display: inline-block;
            width: 2.5vw;
            height: 2.5vw;
            min-width: 12px;
            min-height: 12px;
            background-color: #666;
            border-radius: 50%;
            margin-right: 1.5vw;
        }
        
        /* System info bar - at bottom */
        .system-info-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: rgba(10, 14, 20, 0.95);
            padding: 1vh 3vw;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 2px solid #2ecc40;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }
        
        .system-stats {
            display: flex;
            gap: 4vw;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 1vw;
        }
        
        .stat-label {
            font-size: 2.5vw;
            color: #b0b7c3;
            font-weight: 600;
        }
        
        .stat-value {
            font-size: 3vw;
            color: #fff;
            font-weight: 700;
        }
        
        .cpu-value { color: #2ecc40; }
        .mem-value { color: #3498db; }
        .disk-value { color: #9b59b6; }
        
        .wifi-section {
            display: flex;
            align-items: center;
            gap: 2vw;
        }
        
        .wifi-info {
            text-align: right;
        }
        
        .wifi-ssid {
            font-size: 2.8vw;
            color: #fff;
            font-weight: 600;
            margin-bottom: 0.3vh;
        }
        
        .wifi-instruction {
            font-size: 2.2vw;
            color: #b0b7c3;
        }
        
        .wifi-qr-small {
            width: 10vw;
            min-width: 70px;
            max-width: 100px;
            background: #fff;
            border-radius: 10px;
            padding: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        /* Responsive adjustments */
        @media (max-width: 800px) {
            .info-panels {
                flex-direction: column;
                gap: 2vh;
            }
            
            .panel {
                width: 100%;
            }
            
            .presence-content {
                flex-direction: column;
                gap: 1vh;
            }
            
            .public-clock {
                font-size: 18vw;
            }
            
            .public-date {
                font-size: 5vw;
            }
            
            .panel-title {
                font-size: 4.5vw;
            }
            
            .weather-temp {
                font-size: 12vw;
            }
            
            .weather-desc {
                font-size: 4vw;
            }
            
            .event-date, .event-summary {
                font-size: 3.8vw;
            }
            
            .presence-list li {
                font-size: 3.8vw;
            }
        }
        
        /* For very tall screens */
        @media (min-height: 1800px) {
            .main-container {
                padding-top: 5vh;
            }
            
            .time-section {
                padding: 3vh 4vw;
            }
            
            .panel {
                min-height: 250px;
            }
        }
        
        /* Animation for presence badges */
        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
        
        .present-badge {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="main-container" style="max-width: 900px; width: 95vw; min-width: 0; margin: 0 auto;">
        <!-- Header with logo -->
        <div class="header-section">
            <img class="company-logo" src="/static/Opses_Logo.jpg" alt="Opses Logo" onerror="this.style.display='none'">
        </div>
        
        <!-- Time section -->
        <div class="time-section">
            <div class="public-clock" id="publicclock">
                <span id="clock-hour">00</span><span class="clock-colon">:</span><span id="clock-minute">00</span><span class="clock-colon">:</span><span id="clock-second">00</span>
            </div>
            <div class="public-date">{{ date }}</div>
        </div>
        
        <!-- Info panels (Weather & Calendar side by side) -->
        <div class="info-panels" style="flex-direction: column; gap: 2vh; width: 100%; max-width: 900px;">
            <!-- Weather panel -->
            <div class="panel" style="margin-bottom: 2vh; min-height: 120px;">
                <div class="panel-title">Weather</div>
                <div class="weather-content">
                    {% if weather and weather.temp is defined %}
                    <div class="weather-row">
                        <img class="weather-icon" src="{{ weather.icon_url }}" alt="{{ weather.desc }}" onerror="this.style.display='none'">
                        <span class="weather-temp">{{ weather.temp }}°C</span>
                    </div>
                    <div class="weather-desc">{{ weather.desc }}</div>
                    {% else %}
                    <div class="weather-desc" style="font-size: 4vw; padding: 3vh 0;">Weather data unavailable</div>
                    {% endif %}
                </div>
            </div>
            
            <!-- Calendar panel -->
            <div class="panel" style="min-height: 120px;">
                <div class="panel-title">Events</div>
                <div class="calendar-content">
                    {% if calendar_events and calendar_events|length > 0 %}
                    <ul class="calendar-events-list">
                        {% for event in calendar_events %}
                        <li>
                            <span class="event-date">{{ event.start[5:16] if event.start|length > 16 else event.start }}</span>
                            <span class="event-summary">{{ event.summary }}</span>
                            {% if event.location and event.location|length > 0 %}
                            <span class="event-location">{{ event.location }}</span>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                    {% else %}
                    <div class="no-events">No upcoming events</div>
                    {% endif %}
                </div>
            </div>
        </div>
    
    <!-- System info bar at bottom -->
    <div class="system-info-bar">
        <!-- System status removed as requested -->

        <div class="presence-ticker-bar" style="position: fixed; left: 0; bottom: 0; width: 100vw; height: 3.5vw; background: rgba(24,28,32,0.92); z-index: 200; overflow: hidden; white-space: nowrap; border-top: 2px solid #2ecc40;">
            <div id="presence-ticker" style="display: inline-block; white-space: nowrap; font-size: 2.5vw; position: absolute; left: 100vw; will-change: transform; padding: 0.5vw 0;">
                <span style="color: #2ecc40; font-weight: 700;">Present:</span>
                {% if present_colleagues and present_colleagues|length > 0 %}
                    {% for person in present_colleagues %}
                        <span style="color: #2ecc40; margin-right: 2vw;">{{ person }}</span>
                    {% endfor %}
                {% else %}
                    <span style="color: #888;">No one present</span>
                {% endif %}
                <span style="color: #b0b7c3; font-weight: 700; margin-left: 3vw;">Absent:</span>
                {% if absent_colleagues and absent_colleagues|length > 0 %}
                    {% for person in absent_colleagues %}
                        <span style="color: #b0b7c3; margin-right: 2vw;">{{ person }}</span>
                    {% endfor %}
                {% else %}
                    <span style="color: #888;">None</span>
                {% endif %}
            </div>
        </div>

    <style>
    @keyframes ticker-scroll {
        0% { transform: translateX(100vw); }
        100% { transform: translateX(-100%); }
    }
    </style>
    <script>
    // Animate the presence ticker for smooth continuous scrolling across the full screen
    window.addEventListener('DOMContentLoaded', function() {
        var ticker = document.getElementById('presence-ticker');
        if (ticker) {
            var tickerWidth = ticker.offsetWidth;
            var duration = Math.max(15, tickerWidth / 60); // seconds, adjust speed
            ticker.style.animation = 'ticker-scroll ' + duration + 's linear infinite';
        }
    });
    </script>

        <div class="wifi-section">
            <div class="wifi-info">
                <div class="wifi-ssid">{{ ssid }}</div>
                <div class="wifi-instruction">Scan QR to connect</div>
            </div>
            <img class="wifi-qr-small" src="/wifi_qr" alt="WiFi QR Code">
        </div>
    </div>
    
    <script>
        function pad(n) { return n.toString().padStart(2, '0'); }
        
        function updateClock() {
            try {
                const now = new Date();
                document.getElementById('clock-hour').textContent = pad(now.getHours());
                document.getElementById('clock-minute').textContent = pad(now.getMinutes());
                document.getElementById('clock-second').textContent = pad(now.getSeconds());
            } catch (e) {
                console.error('Clock update error:', e);
            }
        }
        
        // Initial update
        updateClock();
        
        // Update every second
        setInterval(updateClock, 1000);
        
        // Auto-refresh presence data every 30 seconds
        function refreshPresenceData() {
            fetch('/api/presence')
                .then(response => response.json())
                .then(data => {
                    // Update present list
                    const presentList = document.querySelector('.presence-list:first-child');
                    const absentList = document.querySelectorAll('.presence-list')[1];
                    
                    if (presentList && absentList) {
                        // Clear current lists
                        presentList.innerHTML = '';
                        absentList.innerHTML = '';
                        
                        // Update present
                        if (data.present && data.present.length > 0) {
                            data.present.forEach(person => {
                                const li = document.createElement('li');
                                li.innerHTML = '<span class="present-badge"></span>' + person;
                                presentList.appendChild(li);
                            });
                        } else {
                            const li = document.createElement('li');
                            li.innerHTML = '<span class="present-badge"></span>No colleagues detected';
                            li.style.color = '#888';
                            li.style.fontStyle = 'italic';
                            presentList.appendChild(li);
                        }
                        
                        // Update absent
                        if (data.absent && data.absent.length > 0) {
                            data.absent.forEach(person => {
                                const li = document.createElement('li');
                                li.innerHTML = '<span class="absent-badge"></span>' + person;
                                absentList.appendChild(li);
                            });
                        } else {
                            const li = document.createElement('li');
                            li.innerHTML = '<span class="absent-badge"></span>All colleagues present';
                            li.style.color = '#888';
                            li.style.fontStyle = 'italic';
                            absentList.appendChild(li);
                        }
                        
                        // Update counts
                        const presentCount = document.querySelector('.presence-column:first-child div');
                        const absentCount = document.querySelectorAll('.presence-column div')[1];
                        
                        if (presentCount && absentCount) {
                            presentCount.textContent = 'Present (' + data.present.length + ')';
                            absentCount.textContent = 'Absent (' + data.absent.length + ')';
                        }
                        
                        // Update last scan time
                        const now = new Date();
                        document.getElementById('last-scan-time').textContent = 
                            now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    }
                })
                .catch(error => console.error('Error refreshing presence:', error));
        }
        
        // Start auto-refresh every 30 seconds
        setInterval(refreshPresenceData, 30000);
        
        // Also refresh when page becomes visible again
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                refreshPresenceData();
            }
        });
        
        // Initial presence refresh
        setTimeout(refreshPresenceData, 5000);
    </script>
</body>
</html>"""

# =====================
# Flask Routes
# =====================

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Get present/absent colleagues
        present, absent = get_present_absent_colleagues()
        
        # Get system status
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        # Get calendar events
        calendar_events = get_calendar_events()

        # Get weather (with debug output)
        try:
            weather = get_weather() if 'get_weather' in globals() else None
            if not weather:
                print('[DEBUG] Weather unavailable or fetch failed')
        except Exception as e:
            print(f'[DEBUG] Weather fetch error: {e}')
            weather = None

        # Get date from useful_info
        time_info = get_time_info()

        return render_template_string(TEMPLATE,
            date=time_info['date'],
            weather=weather,
            calendar_events=calendar_events,
            present_colleagues=present,
            absent_colleagues=absent,
            sys_status={
                'cpu': round(cpu_percent),
                'mem': round(mem_percent),
                'disk': round(disk_percent)
            },
            ssid=WIFI_SSID
        )
    except Exception as e:
        return f"Error rendering dashboard: {str(e)}", 500

@app.route('/wifi_qr')
def wifi_qr():
    """Generate QR code for WiFi"""
    try:
        # WiFi QR code format
        wifi_string = f"WIFI:S:{WIFI_SSID};T:{WIFI_AUTH};P:{WIFI_PASSWORD};;"
        if not WIFI_SSID or not WIFI_PASSWORD or not WIFI_AUTH:
            print(f"[ERROR] Missing WiFi info: SSID={WIFI_SSID}, AUTH={WIFI_AUTH}, PASS={'***' if WIFI_PASSWORD else ''}")
            return 'WiFi info missing', 500
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(wifi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return send_file(img_bytes, mimetype='image/png')
    except Exception as e:
        print(f"[ERROR] QR code generation failed: {e}")
        return str(e), 500

@app.route('/api/presence')
def api_presence():
    """API endpoint for presence data"""
    try:
        present, absent = get_present_absent_colleagues()
        return jsonify({
            'present': present,
            'absent': absent,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    try:
        return send_from_directory('static', filename)
    except Exception as e:
        return str(e), 404

# =====================
# Start background thread for updates
# =====================
update_thread = threading.Thread(target=background_update_loop, daemon=True)
update_thread.start()

# =====================
# Run the app
# =====================
if __name__ == '__main__':
    print(f"[INFO] Starting dashboard on port 8081...")
    app.run(host='0.0.0.0', port=8081, debug=False, threaded=True)