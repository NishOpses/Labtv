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
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #181c20; margin: 0; padding: 0; }
        .public-container { max-width: 100vw; min-height: 100vh; background: #181c20; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .public-clock { font-size: 7em; font-weight: bold; color: #2ecc40; margin-bottom: 0.2em; letter-spacing: 4px; }
        .public-date { font-size: 3em; color: #fff; margin-bottom: 0.2em; }
        .public-day { font-size: 2.2em; color: #aaa; margin-bottom: 0.5em; }
        .public-host { font-size: 1.5em; color: #2ecc40; margin-bottom: 0.2em; }
        .public-os { font-size: 1.2em; color: #aaa; }
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
        <div class=\"public-clock\" id=\"publicclock\"></div>
        <div class=\"public-date\">{{ date }}</div>
        <div class=\"public-day\">{{ day }}</div>
        <div class=\"public-host\">{{ hostname }}</div>
        <div class=\"public-os\">{{ osinfo }}</div>
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
        date=time_info['date'],
        day=time_info['day'],
        hostname=get_hostname(),
        osinfo=get_os_info()
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
