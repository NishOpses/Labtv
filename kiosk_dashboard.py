from flask import Flask, render_template_string, redirect, url_for
import subprocess
import os
import time
from useful_info import get_time_info, get_hostname, get_os_info

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
            overflow: hidden;
        }
        .public-container {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: linear-gradient(180deg, #181c20 60%, #23272b 100%);
        }
        .company-logo {
            width: 18vw;
            max-width: 180px;
            margin-bottom: 2vh;
        }
        .company-name {
            font-size: 3vw;
            color: #2ecc40;
            font-weight: bold;
            margin-bottom: 2vh;
            letter-spacing: 0.1em;
            text-shadow: 0 2px 12px #000a;
        }
        .public-clock {
            font-size: 10vw;
            font-weight: bold;
            color: #2ecc40;
            margin-bottom: 2vh;
            letter-spacing: 0.1em;
            text-shadow: 0 4px 24px #000a;
        }
        .public-date {
            font-size: 4vw;
            color: #fff;
            margin-bottom: 1vh;
            font-weight: 500;
        }
        .public-day {
            font-size: 3vw;
            color: #aaa;
            margin-bottom: 2vh;
            font-weight: 400;
        }
        @media (orientation: portrait) {
            .public-container {
                padding-top: 8vh;
            }
            .company-logo { width: 22vw; max-width: 220px; }
            .company-name { font-size: 4vw; }
            .public-clock { font-size: 13vw; }
            .public-date { font-size: 5vw; }
            .public-day { font-size: 4vw; }
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
        <img class=\"company-logo\" src=\"https://opses.co.uk/wp-content/uploads/2022/09/cropped-opses-logo-green.png\" alt=\"Opses Logo\">
        <div class=\"company-name\">OPSES</div>
        <div class=\"public-clock\" id=\"publicclock\"></div>
        <div class=\"public-date\">{{ date }}</div>
        <!-- Day removed as per request -->
    </div>
</body>
</html>
"""

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
