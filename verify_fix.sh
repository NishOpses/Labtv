#!/bin/bash
echo "🔧 VERIFICATION SCRIPT FOR KIOSK FIXES"
echo "======================================"
echo "Run Date: $(date)"
echo ""

cd ~/Labtv

echo "1. CHECKING FILE PERMISSIONS..."
chmod +x kiosk.sh network_scanner.py 2>/dev/null
ls -la kiosk.sh network_scanner.py kiosk_dashboard.py

echo ""
echo "2. CHECKING CHROMIUM DIRECTORIES..."
mkdir -p ~/.config/chromium/fault 2>/dev/null
if [ ! -f ~/.config/chromium/fault/Preferences ]; then
    echo '{"exit_type":"Normal","exited_cleanly":true}' > ~/.config/chromium/fault/Preferences
    echo "✅ Created missing Chromium Preferences file"
else
    echo "✅ Chromium Preferences file exists"
fi

echo ""
echo "3. TESTING PYTHON IMPORTS..."
python3 -c "
try:
    import flask, psutil, requests, qrcode, json, subprocess, re
    from datetime import datetime
    print('✅ All core Python packages available')
except ImportError as e:
    print(f'❌ Missing: {e}')
"

echo ""
echo "4. TESTING NETWORK SCANNER..."
python3 -c "
import sys
sys.path.append('.')
try:
    from network_scanner import NetworkScanner
    print('✅ NetworkScanner imported successfully')
    scanner = NetworkScanner()
    print(f'   Loaded {len(scanner.colleagues)} colleagues')
    
    # Quick scan
    present, absent = scanner.detect_presence()
    print(f'   Present: {len(present)}, Absent: {len(absent)}')
    if present:
        print(f'   Present colleagues: {present}')
except Exception as e:
    print(f'❌ Scanner error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "5. TESTING PRESENCE FUNCTIONS FROM KIOSK.SH..."
# Test simple presence function
echo "Testing simple presence function:"
bash -c "
cd ~/Labtv
source kiosk.sh 2>/dev/null
get_presence_info
"

echo ""
echo "Testing advanced presence function:"
bash -c "
cd ~/Labtv
source kiosk.sh 2>/dev/null
get_presence_info_advanced
"

echo ""
echo "6. TESTING DASHBOARD STARTUP..."
timeout 10 python3 kiosk_dashboard.py &
DASH_PID=$!
sleep 3

if curl -s http://localhost:8081 > /dev/null; then
    echo "✅ Dashboard is responding"
    kill $DASH_PID 2>/dev/null
else
    echo "❌ Dashboard not responding"
    kill $DASH_PID 2>/dev/null
    echo "Checking dashboard.log..."
    tail -20 dashboard.log 2>/dev/null
fi

echo ""
echo "7. CHECKING SUDO PERMISSIONS..."
sudo -n arp-scan --version 2>/dev/null && echo "✅ arp-scan sudo OK" || echo "⚠️ arp-scan sudo might need password"
sudo -n ls /root 2>&1 | grep -q "not allowed" && echo "✅ Sudoers config might be working" || echo "⚠️ Check sudoers config"

echo ""
echo "8. CHECKING NETWORK TOOLS..."
which arp-scan && echo "✅ arp-scan installed" || echo "❌ arp-scan not installed"
which nmap && echo "✅ nmap installed" || echo "❌ nmap not installed"
which arp && echo "✅ arp installed" || echo "❌ arp not installed"

echo ""
echo "9. TESTING TEAMS WEBHOOK..."
echo "Testing Teams notification (will send a test message)..."
curl -s -H "Content-Type: application/json" \
  -d "{\"text\": \"🔧 Verification test from $(hostname) at $(date)\"}" \
  "https://opsesuk.webhook.office.com/webhookb2/02968a36-e73c-4b64-aa3f-104718ca7ebb@22ede163-9eae-47d1-963e-11c4a837b9bf/IncomingWebhook/3b048182065a4aa5963427ff5fa554e8/9cbd54cc-3c40-408a-99a1-24dc533f71db/V2wazg9XK8_QrpqzAZLcEh2unetz4sVAjFbEHvtk0fVFA1" \
  && echo "✅ Teams webhook test sent" || echo "❌ Teams webhook failed"

echo ""
echo "======================================"
echo "VERIFICATION COMPLETE"
echo ""
echo "SUMMARY:"
echo "If you see '✅' for most checks, the system is ready."
echo "If you see '❌', address those issues first."
echo ""
echo "To start the kiosk:"
echo "  cd ~/Labtv"
echo "  bash kiosk.sh"
echo ""
echo "To stop the kiosk:"
echo "  pkill -f chromium"
echo "  pkill -f kiosk_dashboard"
echo "  pkill -f kiosk.sh"