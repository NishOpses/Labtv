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
from flask import Flask, render_template_string, send_file, request

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
# MAC Address-based Colleague Presence Detection
# =====================
COLLEAGUES_FILE = os.path.join(os.path.dirname(__file__), "colleagues.json")

def load_colleagues():
    try:
        if not os.path.exists(COLLEAGUES_FILE):
            print(f"[DEBUG] Colleagues file not found: {COLLEAGUES_FILE}")
            return {}
        with open(COLLEAGUES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                print(f"[DEBUG] Loaded {len(data)} colleagues")
                return data
            else:
                print("[DEBUG] Colleagues file is not a dictionary")
                return {}
    except Exception as e:
        print(f"[DEBUG] Error loading colleagues: {e}")
        return {}

def get_arp_table():
    try:
        if platform.system().lower() == "windows":
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        else:
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        return output
    except Exception as e:
        print(f"[DEBUG] Error running arp -a: {e}")
        return ""

def get_present_absent_colleagues():
    try:
        colleagues = load_colleagues()
        arp_table = get_arp_table()
        present = []
        absent = []
        
        if not arp_table:
            print("[DEBUG] ARP table is empty, cannot detect presence")
            return [], []
            
        for name, mac in colleagues.items():
            if mac and mac.lower() in arp_table.lower():
                present.append(name)
            else:
                absent.append(name)
                
        print(f"[DEBUG] Present: {len(present)}, Absent: {len(absent)}")
        return present, absent
    except Exception as e:
        print(f"[DEBUG] Error in get_present_absent_colleagues: {e}")
        return [], []

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
                    event_dt = e.begin.datetime
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=utc)
                    else:
                        event_dt = event_dt.astimezone(utc)
                    
                    # Only show future events (today and next 7 days)
                    if event_dt >= now and event_dt <= now + timedelta(days=7):
                        events.append({
                            "start": event_dt.strftime('%Y-%m-%d %H:%M'),
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
# Clean HTML Template
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
        }
        
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            background: #101217;
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        
        .main-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 2vh;
            width: 100%;
            max-width: 90vw;
            padding: 1vh;
        }
        
        .company-logo {
            width: 18vw;
            max-width: 180px;
            min-width: 100px;
            background: #fff;
            border-radius: 16px;
            margin-bottom: 2vh;
            box-shadow: 0 4px 24px rgba(0,0,0,0.3);
            display: block;
        }
        
        .public-clock {
            font-size: 8vw;
            color: #fff;
            font-weight: bold;
            letter-spacing: 0.08em;
            text-shadow: 0 4px 24px rgba(0,0,0,0.7);
            margin-bottom: 1vh;
            display: flex;
            gap: 1vw;
            justify-content: center;
            align-items: center;
            font-family: 'Courier New', monospace;
        }
        
        .public-date {
            font-size: 2vw;
            color: #fff;
            font-weight: 500;
            margin-bottom: 2vh;
            text-shadow: 0 2px 8px rgba(0,0,0,0.4);
            text-align: center;
        }
        
        .weather-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: #181c20;
            border-radius: 14px;
            padding: 1vh 2vw;
            box-shadow: 0 2px 12px rgba(0,0,0,0.2);
            min-width: 220px;
            max-width: 320px;
            margin-bottom: 2vh;
        }
        
        .weather-row {
            display: flex;
            align-items: center;
            gap: 1vw;
        }
        
        .weather-icon {
            width: 6vw;
            min-width: 60px;
            max-width: 90px;
        }
        
        .weather-temp {
            font-size: 3vw;
            color: #2ecc40;
            font-weight: 700;
            text-shadow: 0 2px 12px rgba(0,0,0,0.4);
        }
        
        .weather-desc {
            font-size: 1.2vw;
            margin-top: 0.5vh;
            color: #eee;
            text-shadow: 0 1px 4px rgba(0,0,0,0.4);
            text-align: center;
        }
        
        .calendar-events {
            background: #181c20;
            border-radius: 14px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.2);
            padding: 1vh 2vw;
            min-width: 220px;
            max-width: 320px;
            width: auto;
            text-align: left;
            margin-bottom: 2vh;
        }
        
        .calendar-events h2 {
            font-size: 1.5vw;
            color: #fff;
            margin: 1vh 0;
            text-align: center;
            text-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }
        
        .calendar-events ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .calendar-events li {
            margin-bottom: 1vh;
            padding-bottom: 1vh;
            border-bottom: 1px solid #333;
        }
        
        .event-date {
            color: #2ecc40;
            font-weight: 700;
            font-size: 1vw;
        }
        
        .event-summary {
            color: #fff;
            font-size: 0.9vw;
            margin-left: 0.5vw;
        }
        
        .event-location {
            color: #aaa;
            font-size: 0.8vw;
            display: block;
            margin-top: 0.2vh;
        }
        
        .no-events {
            color: #aaa;
            font-size: 1vw;
            text-align: center;
            padding: 1vh;
        }
        
        .presence-events {
            position: fixed;
            left: 50%;
            bottom: 2vh;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.2);
            padding: 0.7vh 2vw;
            min-width: 180px;
            z-index: 300;
            text-align: center;
            font-size: 1.2vw;
            max-width: 60vw;
        }
        
        .presence-label {
            font-size: 1.2vw;
            font-weight: 600;
            color: #fff;
            margin-bottom: 0.5vh;
        }
        
        .present {
            color: #2ecc40;
            font-weight: bold;
        }
        
        .absent {
            color: #ff4136;
            font-weight: bold;
        }
        
        .wifi-qr {
            position: fixed;
            left: 2vw;
            bottom: 2vh;
            z-index: 200;
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(0,0,0,0.7);
            padding: 1vw 1.5vw;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        }
        
        .wifi-qr-label {
            color: #fff;
            font-size: 1.2vw;
            margin-bottom: 0.5vh;
            font-weight: 600;
            text-align: center;
        }
        
        .wifi-qr img {
            width: 14vw;
            min-width: 90px;
            max-width: 180px;
            background: #fff;
            border-radius: 10px;
            margin: 0.5vh 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .system-status {
            position: fixed;
            right: 2vw;
            bottom: 2vh;
            background: rgba(0,0,0,0.7);
            color: #fff;
            border-radius: 12px;
            padding: 1vw 1.5vw;
            font-size: 1.2vw;
            box-shadow: 0 4px 24px rgba(0,0,0,0.2);
            font-weight: 500;
            z-index: 200;
        }
        
        .system-status strong {
            color: #2ecc40;
        }
        
        @media (max-width: 700px) {
            .public-clock { font-size: 12vw; }
            .public-date { font-size: 4vw; }
            .weather-temp { font-size: 6vw; }
            .weather-desc { font-size: 3vw; }
            .calendar-events h2 { font-size: 4vw; }
            .event-date { font-size: 3vw; }
            .event-summary { font-size: 3vw; }
            .presence-label { font-size: 3vw; }
            .wifi-qr-label { font-size: 3vw; }
            .system-status { font-size: 3vw; }
        }
        
        .error-message {
            position: fixed;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255, 50, 50, 0.9);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            z-index: 1000;
            font-size: 14px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="error-message" id="errorMessage"></div>
    
    <div class="main-container">
        <img class="company-logo" src="/static/Opses_Logo.jpg" alt="Opses Logo" onerror="this.style.display='none'">
        
        <div class="public-clock" id="publicclock">
            <span id="clock-hour">00</span>:<span id="clock-minute">00</span>:<span id="clock-second">00</span>
        </div>
        
        <div class="public-date">{{ date }}</div>
        
        <div class="weather-container">
            {% if weather and weather.temp is defined %}
            <div class="weather-row">
                <img class="weather-icon" src="{{ weather.icon_url }}" alt="{{ weather.desc }}" onerror="this.style.display='none'">
                <span class="weather-temp">{{ weather.temp }}°C</span>
            </div>
            <div class="weather-desc">{{ weather.desc }}</div>
            {% else %}
            <div class="weather-desc">Weather unavailable</div>
            {% endif %}
        </div>
        
        <div class="calendar-events">
            <h2>Upcoming Events</h2>
            {% if calendar_events and calendar_events|length > 0 %}
                <ul>
                {% for event in calendar_events %}
                    <li>
                        <span class="event-date">{{ event.start[5:16] if event.start|length > 16 else event.start }}</span>
                        <span class="event-summary">{{ event.summary }}</span>
                        {% if event.location and event.location|length > 0 %}
                        <span class="event-location">@ {{ event.location }}</span>
                        {% endif %}
                    </li>
                {% endfor %}
                </ul>
            {% else %}
                <div class="no-events">No upcoming events</div>
            {% endif %}
        </div>
    </div>
    
    <div class="presence-events">
        <div class="presence-label">Lab Presence</div>
        {% if present_colleagues and present_colleagues|length > 0 %}
            <span class="present">Present: </span>
            <span>{{ present_colleagues|join(', ') }}</span>
        {% else %}
            <span class="absent">No colleagues detected</span>
        {% endif %}
    </div>
    
    <div class="wifi-qr">
        <div class="wifi-qr-label">WiFi: {{ ssid }}</div>
        <img src="/wifi_qr" alt="WiFi QR Code" onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"150\" height=\"150\"><rect width=\"150\" height=\"150\" fill=\"white\"/><text x=\"75\" y=\"75\" font-family=\"Arial\" font-size=\"14\" fill=\"black\" text-anchor=\"middle\" alignment-baseline=\"middle\">QR Error</text></svg>';">
        <div class="wifi-qr-label">Scan to connect</div>
    </div>
    
    <div class="system-status">
        <div><strong>CPU:</strong> {{ sys_status.cpu }}%</div>
        <div><strong>RAM:</strong> {{ sys_status.mem }}%</div>
        <div><strong>Disk:</strong> {{ sys_status.disk }}%</div>
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
        
        // Handle image errors
        document.addEventListener('DOMContentLoaded', function() {
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                img.onerror = function() {
                    if (!this.hasAttribute('data-error-handled')) {
                        this.setAttribute('data-error-handled', 'true');
                        console.log('Image failed to load:', this.src);
                    }
                };
            });
        });
        
        // Show error message if any
        const urlParams = new URLSearchParams(window.location.search);
        const error = urlParams.get('error');
        if (error) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = decodeURIComponent(error);
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    </script>
</body>
</html>"""

# =====================
# Routes
# =====================
@app.route("/wifi_qr")
def wifi_qr():
    try:
        qr_str = f"WIFI:T:{WIFI_AUTH};S:{WIFI_SSID};P:{WIFI_PASSWORD};;"
        img = qrcode.make(qr_str)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        print(f"[ERROR] Failed to generate WiFi QR: {e}")
        # Return a simple error image
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (150, 150), color='white')
        d = ImageDraw.Draw(img)
        d.text((75, 75), "QR Error", fill='black', anchor='mm')
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")
WEATHER_API_KEY = "144536c74a836feb69c1cd449b8457b9"
WEATHER_LAT = 51.0902
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15

def get_weather():
    try:
        now = datetime.utcnow()

        # Try cache
        if os.path.exists(WEATHER_CACHE_FILE):
            try:
                with open(WEATHER_CACHE_FILE) as f:
                    data = json.load(f)
                ts = datetime.fromisoformat(data["timestamp"])
                if (now - ts) < timedelta(minutes=WEATHER_CACHE_MINUTES):
                    print(f"[DEBUG] Using cached weather data")
                    return data["weather"]
            except Exception as e:
                print(f"[DEBUG] Error reading weather cache: {e}")

        # Fetch from API
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={WEATHER_LAT}&lon={WEATHER_LON}"
                f"&appid={WEATHER_API_KEY}&units=metric"
            )
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                w = r.json()
                # Weather class for background
                icon = w['weather'][0]['icon']
                desc = w['weather'][0]['description'].lower()
                if 'rain' in desc or 'drizzle' in desc:
                    weather_class = 'rainy'
                elif 'snow' in desc:
                    weather_class = 'snowy'
                elif 'cloud' in desc or icon.startswith('03') or icon.startswith('04'):
                    weather_class = 'cloudy'
                elif 'clear' in desc or icon.startswith('01'):
                    weather_class = 'sunny'
                elif 'thunder' in desc:
                    weather_class = 'stormy'
                elif 'mist' in desc or 'fog' in desc or 'haze' in desc:
                    weather_class = 'foggy'
                else:
                    weather_class = 'default'
                weather = {
                    "temp": int(round(w["main"]["temp"])),
                    "desc": w["weather"][0]["description"].title(),
                    "icon_url": f"https://openweathermap.org/img/wn/{w['weather'][0]['icon']}@4x.png",
                    "weather_class": weather_class
                }
                try:
                    with open(WEATHER_CACHE_FILE, "w") as f:
                        json.dump({"timestamp": now.isoformat(), "weather": weather}, f)
                except Exception as e:
                    print(f"[DEBUG] Error saving weather cache: {e}")
                return weather
            else:
                print(f"[DEBUG] Weather API failed with status {r.status_code}")
                return None
        except Exception as e:
            print(f"[DEBUG] Exception fetching weather: {e}")
            return None
    except Exception as e:
        print(f"[ERROR] Unexpected error in get_weather: {e}")
        return None

def get_system_status():
    try:
        return {
            "cpu": round(psutil.cpu_percent(interval=0.5), 1),
            "mem": round(psutil.virtual_memory().percent, 1),
            "disk": round(psutil.disk_usage("/").percent, 1)
        }
    except Exception as e:
        print(f"[ERROR] Failed to get system status: {e}")
        return {"cpu": 0, "mem": 0, "disk": 0}

@app.route("/")
def public_info():
    try:
        print(f"[DEBUG] Handling request")
        
        # Get all data with error handling
        weather = None
        try:
            weather = get_weather()
        except Exception as e:
            print(f"[ERROR] Weather fetch failed: {e}")
        
        present_colleagues = []
        absent_colleagues = []
        try:
            present_colleagues, absent_colleagues = get_present_absent_colleagues()
        except Exception as e:
            print(f"[ERROR] Colleagues detection failed: {e}")
        
        calendar_events = []
        try:
            calendar_events = get_calendar_events()
        except Exception as e:
            print(f"[ERROR] Calendar events fetch failed: {e}")
        
        sys_status = {}
        try:
            sys_status = get_system_status()
        except Exception as e:
            print(f"[ERROR] System status fetch failed: {e}")
            sys_status = {"cpu": 0, "mem": 0, "disk": 0}
        
        # Get date safely
        date_str = "Loading..."
        try:
            date_info = get_time_info()
            date_str = date_info.get("date", datetime.now().strftime("%A, %d %B %Y"))
        except Exception as e:
            print(f"[ERROR] Date fetch failed: {e}")
            date_str = datetime.now().strftime("%A, %d %B %Y")
        
        # Render template
        return render_template_string(
            TEMPLATE,
            date=date_str,
            weather=weather,
            sys_status=sys_status,
            ssid=WIFI_SSID,
            calendar_events=calendar_events,
            present_colleagues=present_colleagues,
            absent_colleagues=absent_colleagues
        )
        
    except Exception as e:
        print(f"[CRITICAL] Unhandled exception in public_info: {e}")
        print(traceback.format_exc())
        # Return a simple error page
        return """
        <html>
        <head><title>Opses Dashboard - Error</title></head>
        <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
            <div style="text-align: center; padding: 20px;">
                <h1>Opses Lab Dashboard</h1>
                <p style="color: #ff4136;">Temporary error loading dashboard</p>
                <p>Please try refreshing the page.</p>
                <p><small>Error: """ + str(e)[:100] + """</small></p>
            </div>
        </body>
        </html>
        """, 500

@app.errorhandler(404)
def page_not_found(e):
    return """
    <html>
    <head><title>Page Not Found</title></head>
    <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
        <div style="text-align: center;">
            <h1>404 - Page Not Found</h1>
            <p><a href="/" style="color: #2ecc40;">Return to Dashboard</a></p>
        </div>
    </body>
    </html>
    """, 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"[CRITICAL] 500 Error: {e}")
    return """
    <html>
    <head><title>Server Error</title></head>
    <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
        <div style="text-align: center; padding: 20px;">
            <h1>500 - Internal Server Error</h1>
            <p>The dashboard encountered an error.</p>
            <p><a href="/" style="color: #2ecc40;">Try Again</a></p>
        </div>
    </body>
    </html>
    """, 500

# =====================
# Main
# =====================
if __name__ == "__main__":
    print("=" * 60)
    print("Opses Lab Dashboard Starting...")
    print(f"Running on Raspberry Pi: {platform.system()}")
    print(f"Python version: {platform.python_version()}")
    print(f"Server will be available at: http://0.0.0.0:8081")
    print("=" * 60)
    
    # Start background update thread
    try:
        update_thread = threading.Thread(target=background_update_loop, daemon=True)
        update_thread.start()
        print("[DEBUG] Background update thread started")
    except Exception as e:
        print(f"[WARNING] Failed to start background update thread: {e}")
    
    # Run the Flask app
    try:
        # Disable Flask's default logging to reduce noise
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"[CRITICAL] Failed to start Flask server: {e}")
        print(traceback.format_exc())