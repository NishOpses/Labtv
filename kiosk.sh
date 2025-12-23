#!/bin/bash

# Microsoft Teams webhook URL
TEAMS_WEBHOOK_URL="https://opsesuk.webhook.office.com/webhookb2/02968a36-e73c-4b64-aa3f-104718ca7ebb@22ede163-9eae-47d1-963e-11c4a837b9bf/IncomingWebhook/3b048182065a4aa5963427ff5fa554e8/9cbd54cc-3c40-408a-99a1-24dc533f71db/V2wazg9XK8_QrpqzAZLcEh2unetz4sVAjFbEHvtk0fVFA1"

# Function to send notification to Microsoft Teams
send_teams_notification() {
    local message="$1"
    echo "[DEBUG] Sending Teams notification: $message"
    curl -s -H "Content-Type: application/json" -d "{\"text\": \"$message\"}" "$TEAMS_WEBHOOK_URL"
}

# Prevent script from exiting on error
set +e

# Auto-update: Pull latest code from git repository
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ -d .git ]; then
    echo "Updating code from git..."
    git pull
else
    echo "Warning: Not a git repository. Skipping auto-update."
fi

# Set display environment variable for X applications
export DISPLAY=:0

xset s noblank
xset s off
xset -dpms

xdotool mousemove 1080 1920
unclutter -idle 0.5 -root &

sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' /home/$USER/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' /home/$USER/.config/chromium/fault/Preferences

# Function to launch Flask dashboard in background
launch_dashboard() {
    echo "Starting Flask dashboard..."
    # Kill any existing dashboard process
    pkill -f "kiosk_dashboard.py" 2>/dev/null
    sleep 2
    
    # Use python3 and run in background, redirect output to log
    nohup python3 "$SCRIPT_DIR/kiosk_dashboard.py" > "$SCRIPT_DIR/dashboard.log" 2>&1 &
    DASHBOARD_PID=$!
    echo "Dashboard launched with PID $DASHBOARD_PID"
    
    # Wait for dashboard to start
    echo "Waiting for dashboard to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8081 > /dev/null 2>&1; then
            echo "Dashboard is responding"
            return 0
        fi
        sleep 1
    done
    echo "ERROR: Dashboard failed to start"
    return 1
}

# Function to launch Chromium in kiosk mode with dashboard and all other web pages
launch_chromium() {
    # Get the Pi's actual IP address
    PI_IP=$(hostname -I | awk '{print $1}')
    
    # Kill any existing chromium
    pkill -f chromium 2>/dev/null
    sleep 2
    
    /usr/bin/chromium-browser --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=TranslateUI \
        --disable-popup-blocking \
        --start-maximized \
        --kiosk \
        "http://$PI_IP:8081" \
        "https://opses-verto.glide.page/dl/dash" \
        "https://opses-verto.glide.page/dl/orders" \
        "https://opses.co.uk/" &
    CHROMIUM_PID=$!
    echo "Chromium launched with PID $CHROMIUM_PID"
}

# Function to get presence info for notifications
get_presence_info() {
    if command -v python3 &> /dev/null && [ -f "$SCRIPT_DIR/network_scanner.py" ]; then
        PRESENCE_INFO=$(cd "$SCRIPT_DIR" && python3 -c "
import sys
sys.path.append('.')
try:
    from network_scanner import NetworkScanner
    scanner = NetworkScanner()
    present, absent = scanner.detect_presence()
    if present:
        print(f'✅ {len(present)} colleague(s) present: {", ".join(present)}')
    else:
        print('📭 No colleagues detected in office')
except Exception as e:
    print(f'⚠️ Scanner error: {str(e)[:50]}')
" 2>/dev/null)
        echo "$PRESENCE_INFO"
    else
        echo "❌ Scanner not available"
    fi
}

# Initial launch
launch_dashboard
sleep 5  # Give dashboard a moment to start
launch_chromium

# Wait for Chromium to start
sleep 30

# Send notification to Teams with presence info
PRESENCE_INFO=$(get_presence_info)
send_teams_notification "🚀 Kiosk started on $(hostname) at $(date +'%H:%M %d/%m/%Y')
$PRESENCE_INFO
📊 Dashboard: http://$(hostname -I | awk '{print $1}'):8081"

# Refresh all open tabs
sleep 10
xdotool keydown ctrl+shift+r; xdotool keyup ctrl+shift+r;

# Define pages to refresh every 20 minutes (Adjust based on tab order)
TABS_TO_REFRESH=(2 3)  # Example: Refresh 2nd, 4th, and 6th tab (Index starts from 0)

# Initialize timers
tab_switch_timer=0
refresh_timer=0

# Schedule shutdown at 5 PM daily using cron (if not already scheduled)
if ! crontab -l | grep -q "/sbin/shutdown -h now"; then
    echo "0 17 * * * /sbin/shutdown -h now" | crontab -
    echo "Shutdown scheduled at 5 PM daily."
else
    echo "Shutdown cron job already scheduled."
fi

# Add a grace period after launching Chromium to avoid false restarts
GRACE_PERIOD=30
last_launch_time=$(date +%s)
last_presence_notification=""
presence_check_interval=300  # Check presence every 5 minutes
last_presence_check=$(date +%s)

while true; do
    # Health check: Restart Chromium if not running
    if ! pgrep -f chromium > /dev/null; then
        now=$(date +%s)
        if (( now - last_launch_time < GRACE_PERIOD )); then
            echo "[HEALTH CHECK] Skipping restart, within grace period."
        else
            # Try to get last Chromium exit reason
            last_reason="unknown"
            # Check for recent Chromium crash logs
            crash_log=$(ls -t /home/$USER/.config/chromium/Crash\ Reports/*.dmp 2>/dev/null | head -n 1)
            if [ -n "$crash_log" ]; then
                last_reason="crash dump: $crash_log"
            else
                # Check if killed by OOM or signal
                dmesg_out=$(dmesg | tail -n 50 | grep -i chromium | tail -n 1)
                if echo "$dmesg_out" | grep -qi kill; then
                    last_reason="killed: $dmesg_out"
                fi
            fi
            echo "[HEALTH CHECK] Chromium not running! Restarting... Reason: $last_reason"
            send_teams_notification "🔄 Chromium restarted on $(hostname) at $(date +'%H:%M')
Reason: $last_reason"
            launch_chromium
            last_launch_time=$(date +%s)
            sleep 10  # Give Chromium a moment to start
        fi
    else
        echo "[HEALTH CHECK] Chromium is running."
    fi

    # Check dashboard health
    if ! curl -s http://localhost:8081 > /dev/null 2>&1; then
        echo "[HEALTH CHECK] Dashboard not responding, restarting..."
        launch_dashboard
        sleep 5
    fi

    # Periodic presence check and notification
    now=$(date +%s)
    if (( now - last_presence_check >= presence_check_interval )); then
        echo "[PRESENCE CHECK] Checking office presence..."
        CURRENT_PRESENCE=$(get_presence_info)
        if [ "$CURRENT_PRESENCE" != "$last_presence_notification" ]; then
            send_teams_notification "👥 Office Presence Update on $(hostname) at $(date +'%H:%M')
$CURRENT_PRESENCE"
            last_presence_notification="$CURRENT_PRESENCE"
        fi
        last_presence_check=$now
    fi

    # Switch to the next tab every 60 seconds
    xdotool keydown ctrl+Next; xdotool keyup ctrl+Next;
    sleep 60
    ((tab_switch_timer+=60))
    ((refresh_timer+=60))

    # Refresh specific tabs every 20 minutes (1200 seconds)
    if [ $refresh_timer -ge 1200 ]; then
        echo "[TAB REFRESH] Refreshing tabs..."
        for tab in "${TABS_TO_REFRESH[@]}"; do
            xdotool keydown ctrl+$(($tab + 1)); xdotool keyup ctrl+$(($tab + 1));  # Select tab
            sleep 1  # Small delay
            xdotool keydown ctrl+r; xdotool keyup ctrl+r;  # Refresh
            sleep 1  # Small delay
        done
        refresh_timer=0  # Reset refresh timer
    fi
done