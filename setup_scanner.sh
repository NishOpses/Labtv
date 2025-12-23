#!/bin/bash
echo "🔧 Setting up Network Scanner..."
echo "================================"

# Install required tools
echo "1. Installing network scanning tools..."
sudo apt update
sudo apt install -y nmap arp-scan

# Create sudoers file for network scanning
echo "2. Setting up sudo permissions..."
sudo tee /etc/sudoers.d/kiosk-network > /dev/null << EOF
# Allow kiosk user to run network scanning tools
opses ALL=(ALL) NOPASSWD: /usr/bin/arp-scan
opses ALL=(ALL) NOPASSWD: /usr/bin/nmap
EOF

# Test installations
echo "3. Testing installations..."
which nmap && echo "✅ nmap installed" || echo "❌ nmap missing"
which arp-scan && echo "✅ arp-scan installed" || echo "❌ arp-scan missing"

# Test network scanner
echo "4. Testing network scanner..."
cd ~/Labtv
python3 -c "
import sys
sys.path.append('.')
try:
    from network_scanner import NetworkScanner
    scanner = NetworkScanner()
    print('✅ NetworkScanner imported successfully')
    print(f'   Loaded {len(scanner.colleagues)} colleagues')
    print(f'   Network: {scanner.network_range} on {scanner.interface}')
except Exception as e:
    print(f'❌ Error: {e}')
"

echo "5. Testing scanner functionality..."
python3 network_scanner.py

echo ""
echo "🎉 Setup complete!"
echo "To update colleagues, edit the colleagues.json file"
echo "To test the full system: bash kiosk.sh"