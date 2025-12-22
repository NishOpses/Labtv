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
# Calendar Feed Config
# =====================
OUTLOOK_ICAL_URL = os.environ.get("OUTLOOK_ICAL_URL", "https://outlook.office365.com/owa/calendar/744e18cdc1534f5dbcdf3283c76a8f8b@opses.co.uk/85260d62ab584bd69aca5ac9a4223dd84268036899588616720/calendar.ics")
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

# Clear old calendar cache to force new ICS fetch
if os.path.exists(CALENDAR_CACHE_FILE):
    try:
        os.remove(CALENDAR_CACHE_FILE)
        print('[DEBUG] Cleared old calendar cache file to force new ICS fetch.')
    except Exception as e:
        print(f'[DEBUG] Could not remove calendar cache: {e}')

def get_calendar_events():
    print("[DEBUG] get_calendar_events: Called")
    if not OUTLOOK_ICAL_URL:
        print("[DEBUG] No OUTLOOK_ICAL_URL set")
        return []
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
    try:
        print(f"[DEBUG] Fetching ICS feed: {OUTLOOK_ICAL_URL}")
        resp = requests.get(OUTLOOK_ICAL_URL, timeout=10)
        print(f"[DEBUG] ICS HTTP status: {resp.status_code}")
        if resp.status_code == 200:
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
                        "location": getattr(e, 'location', None)
                    })
                    if len(events) >= 5:
                        break
            print(f"[DEBUG] Parsed {len(events)} upcoming events from ICS feed")
            with open(CALENDAR_CACHE_FILE, "w") as f:
                json.dump({"timestamp": now.isoformat(), "events": events}, f)
            return events
        else:
            print(f"[DEBUG] ICS feed fetch failed with status {resp.status_code}")
    except Exception as e:
        print(f"[DEBUG] Exception fetching/parsing ICS feed: {e}")
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
    margin: 0;
    width: 100vw;
    height: 100vh;
    background: #181c20;
    color: #fff;
}
.public-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 7vh;
    padding-bottom: 3vh;
    width: 100vw;
    box-sizing: border-box;
}
.company-logo {
    width: 30vw;
    max-width: 340px;
    background: #fff;
    border-radius: 18px;
    margin-bottom: 2vh;
    box-shadow: 0 4px 24px #0003;
}
.public-clock {
    font-size: 11vw;
    color: #2ecc40;
    font-weight: bold;
    letter-spacing: 0.08em;
    text-shadow: 0 4px 24px #000a;
    margin-bottom: 1vh;
}
.public-date {
    font-size: 6vw;
    color: #fff;
    font-weight: bold;
    margin-bottom: 2vh;
    text-shadow: 0 2px 8px #0006;
}
.weather {
    margin-top: 2vh;
    color: #fff;
    font-size: 4vw;
    font-weight: bold;
    display: flex;
    flex-direction: column;
    align-items: center;
    background: rgba(0,0,0,0.10);
    border-radius: 18px;
    padding: 2vh 4vw;
    box-shadow: 0 2px 12px #0002;
}
.weather-row {
    display: flex;
    align-items: center;
    gap: 3vw;
}
.weather-icon {
    width: 13vw;
    min-width: 120px;
    max-width: 220px;
}
.weather-temp {
    font-size: 8vw;
    color: #2ecc40;
    font-weight: 900;
    margin-left: 2vw;
    text-shadow: 0 2px 12px #0006;
}
.weather-desc {
    font-size: 3vw;
    margin-top: 1vh;
    color: #eee;
    text-shadow: 0 1px 4px #0005;
}
.calendar-events {
    margin-top: 4vh;
    background: rgba(0,0,0,0.13);
    border-radius: 18px;
    box-shadow: 0 2px 12px #0002;
    padding: 2vh 4vw;
    width: 80vw;
    max-width: 900px;
}
.calendar-events h2 {
    font-size: 4vw;
    margin: 2vh 0 2vh 0;
    color: #fff;
    letter-spacing: 0.07em;
    text-shadow: 0 2px 8px #0006;
}
.calendar-events ul {
    list-style: none;
    padding: 0;
    margin: 0;
}
.calendar-events li {
    margin-bottom: 3vh;
    font-size: 4vw;
    color: #fff;
    font-weight: bold;
    line-height: 1.4;
    text-shadow: 0 2px 8px #0006;
}
.calendar-events li span {
    font-size: 4.2vw;
}
.calendar-events li .event-date {
    color: #2ecc40;
    font-weight: 900;
    font-size: 4.2vw;
}
.calendar-events li .event-location {
    color: #aaa;
    font-size: 3vw;
}
.calendar-events .no-events {
    color: #aaa;
    font-size: 3vw;
}
/* Modernized system status and wifi QR backgrounds */
.wifi-qr {
    position: fixed;
    left: 2vw;
    bottom: 2vh;
    margin: 0;
    z-index: 200;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background: #000;
    padding: 1vw 1.5vw;
    border-radius: 16px;
    box-shadow: 0 4px 24px #0002;
}
.wifi-qr img {
    width: 14vw;
    min-width: 90px;
    max-width: 180px;
    background: #fff;
    border-radius: 10px;
    margin-top: 0.5vh;
    box-shadow: 0 2px 8px #0001;
}
/* All text white for visibility */
.wifi-qr-label {
    color: #fff;
    font-size: 1.2vw;
    margin-bottom: 0.5vh;
    font-weight: 600;
}
.system-status {
    position: fixed;
    right: 2vw;
    bottom: 2vh;
    background: #000;
    color: #fff;
    border-radius: 16px;
    padding: 1vw 1.5vw;
    font-size: 1.2vw;
    box-shadow: 0 4px 24px #0002;
    font-weight: 500;
}
.system-status strong {
    color: #2ecc40;
}
@media (max-width: 700px) {
    .public-date, .public-clock, .weather, .calendar-events h2, .calendar-events li {
        font-size: 6vw !important;
    }
    .calendar-events li span, .calendar-events li .event-date {
        font-size: 6vw !important;
    }
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

<body class="weather-{{ weather_class }}">
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
        <h2>Upcoming Events</h2>
        {% if calendar_events and calendar_events|length > 0 %}
            <ul>
            {% for event in calendar_events %}
                <li>
                    <span class="event-date">{{ event.start[5:16] }}</span>
                    &mdash; <span>{{ event.summary }}</span>
                    {% if event.location %}<span class="event-location"> @ {{ event.location }}</span>{% endif %}
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <div class="no-events">No upcoming events</div>
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
                weather = data["weather"]
                # Ensure weather_class is present
                if "weather_class" not in weather:
                    icon = weather.get('icon_url', '')
                    desc = weather.get('desc', '').lower()
                    if 'rain' in desc or 'drizzle' in desc:
                        weather_class = 'rainy'
                    elif 'snow' in desc:
                        weather_class = 'snowy'
                    elif 'cloud' in desc or (icon and (icon.endswith('03.png') or icon.endswith('04.png'))):
                        weather_class = 'cloudy'
                    elif 'clear' in desc or (icon and icon.endswith('01.png')):
                        weather_class = 'sunny'
                    elif 'thunder' in desc:
                        weather_class = 'stormy'
                    elif 'mist' in desc or 'fog' in desc or 'haze' in desc:
                        weather_class = 'foggy'
                    else:
                        weather_class = 'default'
                    weather['weather_class'] = weather_class
                return weather
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
    weather = get_weather()
    return render_template_string(
        TEMPLATE,
        date=get_time_info()["date"],
        weather=weather,
        sys_status=get_system_status(),
        ssid=WIFI_SSID,
        calendar_events=get_calendar_events(),
        weather_class=weather["weather_class"] if weather else "default"
    )

# =====================
# Main
# =====================
if __name__ == "__main__":
    threading.Thread(target=background_update_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False)