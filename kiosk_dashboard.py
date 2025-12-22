
from flask import Flask, render_template_string, send_file
import io
import qrcode
import os
import threading
import time
import subprocess
UPDATE_CHECK_INTERVAL = 3600  # seconds (1 hour)
UPDATE_COMMAND = os.environ.get("KIOSK_UPDATE_COMMAND", "git pull")  # or a custom update script
LAST_UPDATE_FILE = os.path.join(os.path.dirname(__file__), "last_update.txt")

def background_update_loop():
    while True:
        try:
            # Run update command (e.g., git pull or custom script)
            result = subprocess.run(UPDATE_COMMAND, shell=True, capture_output=True, text=True, cwd=os.path.dirname(__file__))
            # Log update result
            with open(LAST_UPDATE_FILE, "w") as f:
                f.write(f"Last checked: {datetime.now().isoformat()}\n")
                f.write(f"Command: {UPDATE_COMMAND}\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"Output:\n{result.stdout}\nErrors:\n{result.stderr}\n")
        except Exception as e:
            with open(LAST_UPDATE_FILE, "a") as f:
                f.write(f"Update error: {e}\n")
        time.sleep(UPDATE_CHECK_INTERVAL)

from flask import Flask, render_template_string
import os
import requests
import json
from datetime import datetime, timedelta
from useful_info import get_time_info

app = Flask(__name__)

WIFI_SSID = os.environ.get("WIFI_SSID", "YourSSID")
WIFI_PASSWORD = os.environ.get("WIFI_PASSWORD", "YourPassword")
WIFI_AUTH = os.environ.get("WIFI_AUTH", "WPA")  # WPA, WEP, or nopass

TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <title>Kiosk Public Info</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no\">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #181c20;
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
            background: linear-gradient(180deg, #181c20 60%, #23272b 100%);
            text-align: center;
            padding-top: 8vh;
        }
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
            font-size: 3vw;
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
            font-size: 2.5vw;
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
        .wifi-qr {
            margin-top: 4vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .wifi-qr img {
            width: 22vw;
            min-width: 120px;
            max-width: 260px;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px #0004;
            margin-bottom: 1vh;
        }
        .wifi-qr-label {
            color: #fff;
            font-size: 1.2vw;
            margin-bottom: 0.5vh;
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
    </script>
</head>
<body>
    <div class=\"public-container\">\n        <img class=\"company-logo\" src=\"/static/Opses_Logo.jpg\" alt=\"OPSES Logo\" onerror=\"this.style.background='#222';this.src='';this.alt='OPSES';\">\n        <div class=\"public-clock\" id=\"publicclock\"></div>\n        <div class=\"public-date\">{{ date }}</div>\n        <div class=\"weather\">\n            {% if weather %}\n            <div class=\"weather-row\">\n                <img class=\"weather-icon\" src=\"{{ weather['icon_url'] }}\" alt=\"Weather\">\n                <span class=\"weather-temp\">{{ weather['temp'] }}°C</span>\n            </div>\n            <div class=\"weather-desc\">{{ weather['desc'] }}</div>\n            {% else %}\n            <div class=\"weather-desc\">Weather unavailable</div>\n            {% endif %}\n        </div>\n        <div class=\"wifi-qr\">\n            <div class=\"wifi-qr-label\">WiFi QR ({{ ssid }})</div>\n            <img src=\"/wifi_qr\" alt=\"WiFi QR Code\">\n            <div class=\"wifi-qr-label\">Scan to connect</div>\n        </div>\n    </div>\n</body>\n</html>\n"""
@app.route("/wifi_qr")
def wifi_qr():
    # WiFi QR code format: WIFI:T:WPA;S:mynetwork;P:mypass;;
    qr_str = f"WIFI:T:{WIFI_AUTH};S:{WIFI_SSID};P:{WIFI_PASSWORD};;"
    img = qrcode.make(qr_str)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

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
    return render_template_string(
        TEMPLATE,
        date=time_info['date'],
        weather=weather,
        ssid=WIFI_SSID
    )

if __name__ == "__main__":
    # Start background update thread (daemon so it won't block exit)
    updater = threading.Thread(target=background_update_loop, daemon=True)
    updater.start()
    app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False)
