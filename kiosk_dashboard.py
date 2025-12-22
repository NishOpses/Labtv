
from flask import Flask, render_template_string, send_file
import io
import qrcode
import os
import requests
import json
from datetime import datetime, timedelta
from useful_info import get_time_info

app = Flask(__name__)


# WiFi QR code config (edit as needed)
WIFI_SSID = "LabWiFi"
WIFI_PASSWORD = "LabPassword123"
WIFI_AUTH = "WPA"  # or "WEP" or "nopass"

# Weather cache file definition
WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")

# Serve QR code image
@app.route("/wifi_qr")
def wifi_qr():
    qr_data = f"WIFI:T:{WIFI_AUTH};S:{WIFI_SSID};P:{WIFI_PASSWORD};;"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

TEMPLATE = """
</style>
<style>
    .health-indicator {
        position: fixed;
        left: 2vw;
        bottom: 2vh;
        background: rgba(24,28,32,0.92);
        color: #fff;
        font-size: 1.2vw;
        padding: 0.7vw 1.5vw;
        border-radius: 1vw;
        box-shadow: 0 2px 12px #0006;
        z-index: 100;
        opacity: 0.92;
        min-width: 180px;
        text-align: left;
        font-family: 'Segoe UI', Arial, sans-serif;
        letter-spacing: 0.03em;
    }
</style>
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <title>Kiosk Public Info</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
        }
        .public-container {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            text-align: center;
            padding-top: 8vh;
        }
        .bg-clear { background: linear-gradient(180deg, #87ceeb 60%, #f0f8ff 100%); }
        .bg-clouds { background: linear-gradient(180deg, #b0bec5 60%, #eceff1 100%); }
        .bg-rain { background: linear-gradient(180deg, #607d8b 60%, #b0bec5 100%); }
        .bg-thunderstorm { background: linear-gradient(180deg, #37474f 60%, #607d8b 100%); }
        .bg-snow { background: linear-gradient(180deg, #e0f7fa 60%, #ffffff 100%); }
        .bg-mist { background: linear-gradient(180deg, #cfd8dc 60%, #eceff1 100%); }
        .bg-default { background: linear-gradient(180deg, #181c20 60%, #23272b 100%); }
        .company-logo {
            width: 32vw;
            max-width: 340px;
            min-width: 160px;
            min-height: 80px;
            margin-bottom: 3vh;
            background: #fff;
            border-radius: 16px;
            object-fit: contain;
            display: block;
            box-shadow: 0 2px 16px #0006;
        }
        .public-clock {
            font-size: 10vw;
            font-weight: bold;
            color: #2ecc40;
            margin-bottom: 2vh;
            letter-spacing: 0.1em;
            text-shadow: 0 4px 24px #000a;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .public-date {
            font-size: 4vw;
            color: #fff;
            margin-bottom: 1vh;
            font-weight: 500;
        }
        .weather {
            margin-top: 2vh;
            color: #fff;
            font-size: 4vw;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .weather-row {
            display: flex;
            align-items: center;
            gap: 2vw;
        }
        .weather-icon {
            width: 8vw;
            min-width: 96px;
            max-width: 180px;
        }
        .weather-temp {
            font-size: 6vw;
            font-weight: 700;
            color: #2ecc40;
        }
        .weather-desc {
            font-size: 3vw;
            color: #eee;
            margin-top: 1vh;
            text-align: center;
        }
        @media (orientation: portrait) {
            .public-container {
                padding-top: 8vh;
            }
            .company-logo { width: 30vw; max-width: 320px; min-width: 140px; }
            .public-clock { font-size: 13vw; }
            .public-date { font-size: 5vw; }
        }
</style>
<style>
    .status-indicator {
        position: fixed;
        right: 2vw;
        bottom: 2vh;
        background: rgba(24,28,32,0.92);
        color: #fff;
        font-size: 1.5vw;
        padding: 0.7vw 1.5vw;
        border-radius: 1vw;
        box-shadow: 0 2px 12px #0006;
        z-index: 100;
        opacity: 0.92;
        min-width: 180px;
        text-align: right;
        font-family: 'Segoe UI', Arial, sans-serif;
        letter-spacing: 0.03em;
    }
</style>
<script>
function updateClock() {
    var now = new Date();
    var time = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
    var pubclock = document.getElementById('publicclock');
    if (pubclock) pubclock.textContent = time;
}
setInterval(updateClock, 1000);
window.onload = updateClock;

function updateStatus() {
    fetch('/status').then(r => r.json()).then(data => {
        var el = document.getElementById('status-indicator');
        if (el) {
            el.textContent = data.status;
        }
    });
}
setInterval(updateStatus, 30000);
window.onload = function() { updateClock(); updateStatus(); };
</script>
</head>
<body>
    <div class=\"public-container {{ bg_class }}\">
        <img class=\"company-logo\" src=\"/static/Opses_Logo.jpg\" alt=\"OPSES Logo\" onerror=\"this.style.background='#222';this.src='';this.alt='OPSES';\">
        <div class=\"public-clock\" id=\"publicclock\"></div>
        <div style="position:fixed; bottom:2vh; right:2vw; z-index:101; display:flex; flex-direction:column; align-items:center;">
            <img src="/wifi_qr" alt="WiFi QR" style="width:120px; height:120px; background:#fff; border-radius:16px; box-shadow:0 2px 12px #0006; margin-bottom:0.5vw;">
            <div style="color:#fff; font-size:1vw; text-align:center; background:rgba(24,28,32,0.7); border-radius:0.5vw; padding:0.2vw 0.7vw;">WiFi: {{ ssid }}</div>
        </div>
        <div class=\"public-date\">{{ date }}</div>
        <div class=\"weather\">
            {% if weather %}
            <div class=\"weather-row\">
                <img class=\"weather-icon\" src=\"{{ weather['icon_url'] }}\" alt=\"Weather\">
                <span class=\"weather-temp\">{{ weather['temp'] }}°C</span>
            </div>
            <div class=\"weather-desc\">{{ weather['desc'] }}</div>
            {% else %}
            <div class=\"weather-desc\">Weather unavailable</div>
            {% endif %}
        </div>
    </div>
    <div class="status-indicator" id="status-indicator">Loading status...</div>
    <div class="health-indicator" id="health-indicator">Loading health...</div>
</body>
</html>
"""

import platform
import psutil
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15  # 96 calls/day max

def get_weather():
    def get_bg_class(weather):
        if not weather or 'desc' not in weather:
            return 'bg-default'
        desc = weather['desc'].lower()
        if 'clear' in desc:
            return 'bg-clear'
        if 'cloud' in desc:
            return 'bg-clouds'
        if 'rain' in desc or 'drizzle' in desc:
            return 'bg-rain'
        if 'thunder' in desc:
            return 'bg-thunderstorm'
        if 'snow' in desc:
            return 'bg-snow'
        if 'mist' in desc or 'fog' in desc or 'haze' in desc:
            return 'bg-mist'
        return 'bg-default'
    now = datetime.utcnow()
    # Try cache
    if os.path.exists(WEATHER_CACHE_FILE):
        try:
            with open(WEATHER_CACHE_FILE, "r") as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data.get("timestamp"))
            if (now - ts) < timedelta(minutes=WEATHER_CACHE_MINUTES):
                return data["weather"]
        except Exception:
            pass
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
            return weather
    except Exception:
        pass
    return None

@app.route("/")
def public_info():
    time_info = get_time_info()
    weather = get_weather()
    bg_class = get_bg_class(weather)
    return render_template_string(
        TEMPLATE,
        date=time_info['date'],
        weather=weather,
        bg_class=bg_class,
        ssid=WIFI_SSID
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)

def get_chromium_status():
    try:
        out = subprocess.check_output(["pgrep", "-f", "chromium"]).decode().strip()
        return f"Running (PID: {out.splitlines()[0]})"
    except subprocess.CalledProcessError:
        return "Not running"

def get_last_reason():
    # Try to find the last restart reason from a file (if your script writes it)
    reason_file = os.path.join(os.path.dirname(__file__), "last_chromium_reason.txt")
    if os.path.exists(reason_file):
        with open(reason_file) as f:
            return f.read().strip()
    return "Unknown or not recorded"

def get_uptime():
    with open("/proc/uptime") as f:
        seconds = float(f.read().split()[0])
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return f"{d}d {h}h {m}m {s}s"

def get_recent_log():
    try:
        out = subprocess.check_output(["tail", "-n", "30", "kiosk.log"]).decode()
        return out
    except Exception:
        return "No log file found."




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
