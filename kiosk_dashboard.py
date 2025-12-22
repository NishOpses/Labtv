import os
import io
import qrcode
import psutil
import threading
import time
import subprocess
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, send_file
from useful_info import get_time_info
from ics import Calendar

# =====================
# Announcement config
# =====================
ANNOUNCEMENT_FILE = os.path.join(os.path.dirname(__file__), "announcements.json")

def get_announcement():
    try:
        with open(ANNOUNCEMENT_FILE, "r") as f:
            data = json.load(f)
            return data.get("announcement", "")
    except Exception:
        return ""

# =====================
# Calendar Feed Config
# =====================
OUTLOOK_ICAL_URL = os.environ.get(
    "OUTLOOK_ICAL_URL",
    "https://outlook.office365.com/owa/calendar/744e18cdc1534f5dbcdf3283c76a8f8b@opses.co.uk/85260d62ab584bd69aca5ac9a4223dd84268036899588616720/calendar.ics"
)
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

def get_calendar_events():
    import pytz
    utc = pytz.UTC
    now = datetime.utcnow().replace(tzinfo=utc)

    if os.path.exists(CALENDAR_CACHE_FILE):
        try:
            with open(CALENDAR_CACHE_FILE, "r") as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data["timestamp"])
            if (now - ts) < timedelta(minutes=CALENDAR_CACHE_MINUTES):
                return data["events"]
        except Exception:
            pass

    try:
        resp = requests.get(OUTLOOK_ICAL_URL, timeout=10)
        if resp.status_code == 200:
            c = Calendar(resp.text)
            events = []
            for e in sorted(c.timeline, key=lambda ev: ev.begin):
                dt = e.begin.datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=utc)
                else:
                    dt = dt.astimezone(utc)

                if now <= dt <= now + timedelta(days=7):
                    events.append({
                        "start": dt.strftime('%Y-%m-%d %H:%M'),
                        "summary": e.name or "(No Title)",
                        "location": getattr(e, "location", None)
                    })
                if len(events) >= 5:
                    break

            with open(CALENDAR_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "events": events}, f)

            return events
    except Exception:
        pass

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
        except Exception as e:
            with open(LAST_UPDATE_FILE, "a") as f:
                f.write(f"Update error: {e}\n")

        time.sleep(UPDATE_CHECK_INTERVAL)

# =====================
# Weather
# =====================
WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")
WEATHER_API_KEY = "144536c74a836feb69c1cd449b8457b9"
WEATHER_LAT = 51.0902
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15

def get_weather():
    now = datetime.utcnow()

    if os.path.exists(WEATHER_CACHE_FILE):
        try:
            with open(WEATHER_CACHE_FILE) as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data["timestamp"])
            if (now - ts) < timedelta(minutes=WEATHER_CACHE_MINUTES):
                return data["weather"]
        except Exception:
            pass

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={WEATHER_LAT}&lon={WEATHER_LON}"
            f"&appid={WEATHER_API_KEY}&units=metric"
        )
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            w = r.json()
            weather = {
                "temp": int(round(w["main"]["temp"])),
                "desc": w["weather"][0]["description"].title(),
                "icon_url": f"https://openweathermap.org/img/wn/{w['weather'][0]['icon']}@4x.png",
                "weather_class": "default"
            }
            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "weather": weather}, f)
            return weather
    except Exception:
        pass

    return None

def get_system_status():
    return {
        "cpu": psutil.cpu_percent(interval=0.5),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    }

# =====================
# Routes
# =====================
@app.route("/wifi_qr")
def wifi_qr():
    qr_str = f"WIFI:T:{WIFI_AUTH};S:{WIFI_SSID};P:{WIFI_PASSWORD};;"
    img = qrcode.make(qr_str)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/")
def public_info():
    weather = get_weather()
    return render_template_string(
        TEMPLATE,
        date=get_time_info()["date"],
        weather=weather,
        weather_class=weather["weather_class"] if weather else "default",
        sys_status=get_system_status(),
        calendar_events=get_calendar_events(),
        ssid=WIFI_SSID,
        announcement=get_announcement()
    )

# =====================
# Main
# =====================
if __name__ == "__main__":
    threading.Thread(target=background_update_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False)
