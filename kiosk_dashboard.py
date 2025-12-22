from ics import Calendar

# =====================
# Google Calendar Feed Config
# =====================
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
# Google Calendar Feed Config
# =====================
GOOGLE_ICAL_URL = os.environ.get("GOOGLE_ICAL_URL", "https://calendar.google.com/calendar/ical/00e62f5d1cd53fe8c514d10962c7dc1e53c2a238ef907c5d4422e3f4edad0718%40group.calendar.google.com/public/basic.ics")
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

def get_calendar_events():
    if not GOOGLE_ICAL_URL:
        return []
    now = datetime.utcnow()
    # Try cache
    if os.path.exists(CALENDAR_CACHE_FILE):
        try:
            with open(CALENDAR_CACHE_FILE, "r") as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data.get("timestamp"))
            if (now - ts) < timedelta(minutes=CALENDAR_CACHE_MINUTES):
                return data["events"]
        except Exception:
            pass
    # Fetch from iCal feed
    try:
        resp = requests.get(GOOGLE_ICAL_URL, timeout=10)
        if resp.status_code == 200:
            c = Calendar(resp.text)
            events = []
            for e in sorted(c.timeline, key=lambda ev: ev.begin):
                # Only show future events (today and next 7 days)
                if e.begin.datetime >= now and e.begin.datetime <= now + timedelta(days=7):
                    events.append({
                        "start": e.begin.format('YYYY-MM-DD HH:mm'),
                        "summary": e.name or "(No Title)",
                        "location": getattr(e, 'location', None)
                    })
                    if len(events) >= 5:
                        break
            with open(CALENDAR_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "events": events}, f)
            return events
    except Exception:
        pass
    return []
from flask import Flask, render_template_string, send_file
import io
import qrcode
import os
import psutil
import threading
import time
import subprocess
import requests
import json
from datetime import datetime, timedelta
from useful_info import get_time_info

# =====================
# App setup
# =====================
app = Flask(__name__)

WIFI_SSID = os.environ.get("WIFI_SSID", "YourSSID")
WIFI_PASSWORD = os.environ.get("WIFI_PASSWORD", "YourPassword")
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
# HTML Template
# =====================
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Kiosk Public Info</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

<style>
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #181c20;
    margin: 0;
    width: 100vw;
    height: 100vh;
}
.public-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 8vh;
}
.company-logo {
    width: 32vw;
    max-width: 340px;
    background: #fff;
    border-radius: 16px;
    margin-bottom: 3vh;
}
.public-clock {
    font-size: 10vw;
    color: #2ecc40;
    font-weight: bold;
}
.public-date {
    font-size: 4vw;
    color: #fff;
}
    .weather {
        margin-top: 2vh;
        color: #fff;
        font-size: 4vw;
        font-weight: bold;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .weather-row {
        display: flex;
        align-items: center;
        gap: 3vw;
    }
    .weather-icon {
        width: 12vw;
        min-width: 140px;
        max-width: 260px;
    }
    .weather-temp {
        font-size: 8vw;
        color: #2ecc40;
        font-weight: 900;
        margin-left: 2vw;
    }
    .weather-desc {
        font-size: 3vw;
        margin-top: 1vh;
        color: #eee;
    }
    .wifi-qr {
        position: fixed;
        left: 2vw;
        bottom: 2vh;
        margin: 0;
        z-index: 200;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        background: rgba(24,28,32,0.92);
        padding: 1vw 1.5vw;
        border-radius: 14px;
        box-shadow: 0 2px 12px #0004;
    }
    .wifi-qr img {
        width: 14vw;
        min-width: 90px;
        max-width: 180px;
        background: #fff;
        border-radius: 10px;
        margin-top: 0.5vh;
    }
    .wifi-qr-label {
        color: #fff;
        font-size: 1.2vw;
        margin-bottom: 0.5vh;
    }
.system-status {
    position: fixed;
    right: 2vw;
    bottom: 2vh;
    background: rgba(30,34,40,0.92);
    color: #fff;
    border-radius: 12px;
    padding: 1vw 1.5vw;
    font-size: 1.2vw;
}
.system-status strong {
    color: #2ecc40;
}
</style>

<script>
function updateClock() {
    const now = new Date();
    document.getElementById("publicclock").textContent =
        now.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
}
setInterval(updateClock, 1000);
window.onload = updateClock;
</script>
</head>

<body>
<div class="public-container">
    <img class="company-logo" src="/static/Opses_Logo.jpg" alt="OPSES Logo">

    <div class="public-clock" id="publicclock"></div>
    <div class="public-date">{{ date }}</div>


    <div class="weather">
        {% if weather %}
        <div class="weather-row">
            <img class="weather-icon" src="{{ weather.icon_url }}">
            <span class="weather-temp">{{ weather.temp }}°C</span>
        </div>
        <div class="weather-desc">{{ weather.desc }}</div>
        {% else %}
        <div class="weather-desc">Weather unavailable</div>
        {% endif %}
    </div>

    <div class="calendar-events">
        <h2 style="font-size:2vw;margin:2vh 0 1vh 0;color:#fff;">Upcoming Events</h2>
        {% if calendar_events and calendar_events|length > 0 %}
            <ul style="list-style:none;padding:0;margin:0;">
            {% for event in calendar_events %}
                <li style="margin-bottom:1vh;font-size:1.5vw;color:#fff;">
                    <span style="color:#2ecc40;font-weight:bold;">{{ event.start[5:16] }}</span>
                    &mdash; {{ event.summary }}
                    {% if event.location %}<span style="color:#aaa;">@ {{ event.location }}</span>{% endif %}
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <div style="color:#aaa;font-size:1.2vw;">No upcoming events</div>
        {% endif %}
    </div>

    <!-- QR code moved to bottom left -->
    <div class="wifi-qr">
        <div class="wifi-qr-label">WiFi: {{ ssid }}</div>
        <img src="/wifi_qr">
        <div class="wifi-qr-label">Scan to connect</div>
    </div>
</div>

<div class="system-status">
    <div><strong>CPU:</strong> {{ sys_status.cpu }}%</div>
    <div><strong>RAM:</strong> {{ sys_status.mem }}%</div>
    <div><strong>Disk:</strong> {{ sys_status.disk }}%</div>
</div>

</body>
</html>
"""

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
                "icon_url": f"https://openweathermap.org/img/wn/{w['weather'][0]['icon']}@4x.png"
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

@app.route("/")
def public_info():
    return render_template_string(
        TEMPLATE,
        date=get_time_info()["date"],
        weather=get_weather(),
        sys_status=get_system_status(),
        ssid=WIFI_SSID,
        calendar_events=get_calendar_events()
    )

# =====================
# Main
# =====================
if __name__ == "__main__":
    threading.Thread(target=background_update_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False)
