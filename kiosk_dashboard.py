
from flask import Flask, render_template_string
import os
import requests
import json
from datetime import datetime, timedelta
from useful_info import get_time_info

app = Flask(__name__)

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
            font-size: 2vw;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .weather-row {
            display: flex;
            align-items: center;
            gap: 1vw;
        }
        .weather-icon {
            width: 4vw;
            min-width: 48px;
            max-width: 80px;
        }
        .weather-temp {
            font-size: 3vw;
            font-weight: 600;
            color: #2ecc40;
        }
        .weather-desc {
            font-size: 1.5vw;
            color: #eee;
            margin-top: 0.5vh;
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
    <div class=\"public-container\">
        <img class=\"company-logo\" src=\"/static/Opses_Logo.jpg\" alt=\"OPSES Logo\" onerror=\"this.style.background='#222';this.src='';this.alt='OPSES';\">
        <div class=\"public-clock\" id=\"publicclock\"></div>
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
</body>
</html>
"""

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
        weather=weather
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

@app.route("/")

# Redirect root to /public so the kiosk always starts with the public info tab
@app.route("/")
def public_info():
    time_info = get_time_info()
    return render_template_string(
        TEMPLATE,
        date=time_info['date']
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
