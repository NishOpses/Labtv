from flask import Flask, render_template_string
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
    <title>Kiosk Status Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 700px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px #ccc; }
        h1 { color: #333; }
        .status { font-size: 1.2em; margin-bottom: 20px; }
        .log { background: #222; color: #eee; padding: 10px; border-radius: 4px; font-size: 0.95em; max-height: 200px; overflow-y: auto; }
        .info { margin-bottom: 20px; }
        .clock { font-size: 2em; font-weight: bold; color: #2a2; margin-bottom: 10px; }
    </style>
    <script>
    function updateClock() {
        var now = new Date();
        var time = now.toLocaleTimeString();
        document.getElementById('liveclock').textContent = time;
    }
    setInterval(updateClock, 1000);
    window.onload = updateClock;
    </script>
</head>
<body>
    <div class=\"container\">
        <h1>Kiosk Status Dashboard</h1>
        <div class=\"info\">
            <div class=\"clock\"><span id=\"liveclock\"></span></div>
            <strong>Date:</strong> {{ date }}<br>
            <strong>Day:</strong> {{ day }}<br>
            <strong>Hostname:</strong> {{ hostname }}<br>
            <strong>OS:</strong> {{ osinfo }}<br>
        </div>
        <div class=\"status\">
            <strong>Chromium Status:</strong> {{ chromium_status }}<br>
            <strong>Last Restart Reason:</strong> {{ last_reason }}<br>
            <strong>System Uptime:</strong> {{ uptime }}<br>
        </div>
        <h2>Recent Log</h2>
        <div class=\"log\">
            <pre>{{ log }}</pre>
        </div>
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
def dashboard():
    time_info = get_time_info()
    return render_template_string(
        TEMPLATE,
        chromium_status=get_chromium_status(),
        last_reason=get_last_reason(),
        uptime=get_uptime(),
        log=get_recent_log(),
        date=time_info['date'],
        day=time_info['day'],
        hostname=get_hostname(),
        osinfo=get_os_info()
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
