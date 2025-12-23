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
from flask import Flask, render_template_string, send_file, request, jsonify

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
# Optimized HTML Template for Portrait 1080x1920
# =====================
# [TEMPLATE CODE REMAINS THE SAME AS BEFORE - TOO LONG TO DUPLICATE]
# This is the same modern template we created earlier

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

@app.route("/api/presence")
def api_presence():
    """API endpoint for presence data"""
    try:
        present, absent = get_present_absent_colleagues()
        return jsonify({
            "present": present,
            "absent": absent,
            "timestamp": datetime.now().isoformat(),
            "total": len(present) + len(absent)
        })
    except Exception as e:
        print(f"[ERROR] API presence error: {e}")
        return jsonify({
            "present": [],
            "absent": [],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

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
    print(f"Network Scanner Available: {NETWORK_SCANNER_AVAILABLE}")
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
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"[CRITICAL] Failed to start Flask server: {e}")
        print(traceback.format_exc())