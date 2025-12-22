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
# App setup
# =====================
app = Flask(__name__)

# =====================
# Announcement
# =====================
ANNOUNCEMENT_FILE = os.path.join(os.path.dirname(__file__), "announcements.json")

def get_announcement():
    try:
        with open(ANNOUNCEMENT_FILE, "r") as f:
            return json.load(f).get("announcement", "")
    except Exception:
        return ""

# =====================
# Calendar
# =====================
OUTLOOK_ICAL_URL = os.environ.get("OUTLOOK_ICAL_URL")
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

def get_calendar_events():
    if not OUTLOOK_ICAL_URL:
        return []

    import pytz
    utc = pytz.UTC
    now = datetime.utcnow().replace(tzinfo=utc)

    if os.path.exists(CALENDAR_CACHE_FILE):
        try:
            with open(CALENDAR_CACHE_FILE) as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data["timestamp"])
            if (now - ts) < timedelta(minutes=CALENDAR_CACHE_MINUTES):
                return data["events"]
        except Exception:
            pass

    try:
        r = requests.get(OUTLOOK_ICAL_URL, timeout=10)
        if r.status_code == 200:
            cal = Calendar(r.text)
            events = []

            for e in sorted(cal.timeline, key=lambda ev: ev.begin):
                dt = e.begin.datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=utc)

                if now <= dt <= now + timedelta(days=7):
                    events.append({
                        "start": dt.strftime("%Y-%m-%d %H:%M"),
                        "summary": e.name or "No title",
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
# Weather
# =====================
WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")
WEATHER_API_KEY = "144536c74a836feb69c1cd449b8457b9"
WEATHER_LAT = 51.0902
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15

def classify_weather(desc: str):
    d = desc.lower()
    if "rain" in d:
        return "rainy"
    if "snow" in d:
        return "snowy"
    if "cloud" in d:
        return "cloudy"
    if "clear" in d:
        return "sunny"
    if "fog" in d or "mist" in d:
        return "foggy"
    return "default"

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
                "weather_class": classify_weather(w["weather"][0]["description"])
            }
            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "weather": weather}, f)
            return weather
    except Exception:
        pass

    return None

# =====================
# System status
# =====================
def get_system_status():
    return {
        "cpu": psutil.cpu_percent(interval=0.3),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    }

# =====================
# HTML TEMPLATE (THIS WAS MISSING)
# =====================
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Lab Kiosk</title>
<style>
body { background:#181c20; color:white; font-family:Arial; text-align:center; }
.clock { font-size:6vw; margin-top:2vh; }
.announcement { background:#2ecc40; color:#111; padding:1vh; margin:2vh auto; width:80vw; border-radius:10px; }
.status { position:fixed; right:2vw; bottom:2vh; background:black; padding:1vh 2vw; border-radius:12px; }
.wifi { position:fixed; left:2vw; bottom:2vh; }
</style>
</head>
<body>

{% if announcement %}
<div class="announcement">{{ announcement }}</div>
{% endif %}

<div class="clock">{{ date }}</div>

{% if weather %}
<div>{{ weather.temp }}°C – {{ weather.desc }}</div>
{% endif %}

<h3>Upcoming Events</h3>
{% for e in calendar_events %}
<div>{{ e.start }} – {{ e.summary }}</div>
{% endfor %}

<div class="wifi">
    <div>WiFi: {{ ssid }}</div>
    <img src="/wifi_qr" width="140">
</div>

<div class="status">
CPU {{ sys_status.cpu }}%<br>
RAM {{ sys_status.mem }}%<br>
Disk {{ sys_status.disk }}%
</div>

</body>
</html>
"""

# =====================
# Routes
# =====================
@app.route("/wifi_qr")
def wifi_qr():
    qr = qrcode.make(f"WIFI:T:WPA;S:{WIFI_SSID};P:{WIFI_PASSWORD};;")
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

WIFI_SSID = "Opses_Global_Guest"
WIFI_PASSWORD = "Covert3791Beer105%"

@app.route("/")
def public_info():
    weather = get_weather()
    return render_template_string(
        TEMPLATE,
        date=get_time_info()["date"],
        weather=weather,
        sys_status=get_system_status(),
        calendar_events=get_calendar_events(),
        announcement=get_announcement(),
        ssid=WIFI_SSID
    )

# =====================
# Main
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
