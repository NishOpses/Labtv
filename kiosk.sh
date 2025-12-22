
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


# Function to launch Chromium in kiosk mode
launch_chromium() {
    /usr/bin/chromium-browser --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-features=TranslateUI \
        --disable-popup-blocking \
        --start-maximized \
        --kiosk \
        "https://opses-verto.glide.page/dl/dash" \
        "https://opses-verto.glide.page/dl/orders" \
        "https://opses-company.monday.com/boards/1790536551" \
        "https://opses-company.monday.com/boards/1809770010/views/25272562" \
        "https://opses.co.uk/" &
    CHROMIUM_PID=$!
    echo "Chromium launched with PID $CHROMIUM_PID"
}



# Initial launch
launch_chromium

# Wait for Chromium to start
sleep 120

# Send notification to Teams when script is fully initialized (function is now defined)
send_teams_notification "Kiosk script started successfully on $(hostname) at $(date)"


# Function to check if the "Login" screen is visible and press Enter
check_and_login() {
    # Check if the login screen is visible by looking for a known element (e.g., a login button or specific UI element)
    # This is a basic approach assuming a login button or field appears when logged out.
    
    # Change this to fit the specific login screen UI element
    export DISPLAY=:0
    
    if xdotool search --onlyvisible  --name "monday.com" getwindowname; then
        echo "Logged out, attempting to log in..."
        xdotool key Return  # Simulate pressing Enter
        xdotool key Return
    fi
}


# Refresh all open tabs
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




while true; do
    # Health check: Restart Chromium if not running
    if ! pgrep -x "chromium-browser" > /dev/null; then
        echo "[HEALTH CHECK] Chromium not running! Restarting..."
        send_teams_notification "Chromium was restarted on $(hostname) at $(date)"
        launch_chromium
        sleep 10  # Give Chromium a moment to start
    else
        echo "[HEALTH CHECK] Chromium is running."
    fi


    # Check if logged out from Monday and log in if necessary
    check_and_login

    # Switch to the next tab every 60 seconds
    xdotool keydown ctrl+Next; xdotool keyup ctrl+Next;
    sleep 60
    ((tab_switch_timer+=60))
    ((refresh_timer+=60))

    # Refresh specific tabs every 20 minutes (1200 seconds)
    if [ $refresh_timer -ge 1200 ]; then
        for tab in "${TABS_TO_REFRESH[@]}"; do
            xdotool keydown ctrl+$(($tab + 1)); xdotool keyup ctrl+$(($tab + 1));  # Select tab
            sleep 1  # Small delay
            xdotool keydown ctrl+r; xdotool keyup ctrl+r;  # Refresh
            sleep 1  # Small delay
        done
        refresh_timer=0  # Reset refresh timer
    fi
done
