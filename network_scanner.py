#!/usr/bin/env python3
"""
Simplified Office Presence Scanner
Scans network for MAC addresses to detect colleague presence
"""

import subprocess
import json
import re
import os
import time
from datetime import datetime
from typing import List, Tuple, Dict, Optional

class NetworkScanner:
    """Network scanner for detecting devices via MAC addresses"""
    
    def __init__(self, config_file: str = "colleagues.json"):
        """
        Initialize the network scanner
        
        Args:
            config_file: Path to colleagues JSON file
        """
        self.config_file = config_file
        self.colleagues = self._load_colleagues()
        print(f"[SCANNER] Loaded {len(self.colleagues)} colleagues")
    
    def _load_colleagues(self) -> Dict[str, str]:
        """Load colleagues from JSON file"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            colleagues_path = os.path.join(script_dir, self.config_file)
            
            if not os.path.exists(colleagues_path):
                print(f"[SCANNER] Colleagues file not found: {colleagues_path}")
                return {}
            
            with open(colleagues_path, 'r') as f:
                colleagues = json.load(f)
            
            # Normalize MAC addresses
            validated = {}
            for name, mac in colleagues.items():
                normalized = self._normalize_mac(mac)
                if normalized:
                    validated[name] = normalized
                else:
                    print(f"[SCANNER] Invalid MAC for {name}: {mac}")
            
            return validated
            
        except Exception as e:
            print(f"[SCANNER] Failed to load colleagues: {e}")
            return {}
    
    def _normalize_mac(self, mac: str) -> Optional[str]:
        """Normalize MAC address to consistent format (AA:BB:CC:DD:EE:FF)"""
        if not mac:
            return None
        
        # Remove separators and convert to uppercase
        clean = re.sub(r'[^a-fA-F0-9]', '', mac)
        
        # Check if it's a valid MAC
        if len(clean) != 12:
            return None
        
        # Format as AA:BB:CC:DD:EE:FF
        normalized = ':'.join(clean[i:i+2] for i in range(0, 12, 2))
        return normalized.upper()
    
    def scan_with_arp(self) -> List[Dict]:
        """Scan using arp-scan"""
        devices = []
        
        try:
            # Check if arp-scan is installed
            check = subprocess.run(['which', 'arp-scan'], 
                                 capture_output=True, text=True)
            if not check.stdout.strip():
                print("[SCANNER] arp-scan not installed")
                return devices
            
            # Run arp-scan
            cmd = ['sudo', 'arp-scan', '--localnet', '--retry=2', '--timeout=1000']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            # Parse output
            for line in result.stdout.split('\n'):
                # Skip header/footer lines
                if not line or 'arp-scan' in line or 'packets' in line:
                    continue
                
                # Parse: IP<TAB>MAC<TAB>Vendor
                parts = line.split('\t')
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    raw_mac = parts[1].strip()
                    
                    if re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', raw_mac):
                        devices.append({
                            'ip': ip,
                            'mac': self._normalize_mac(raw_mac),
                            'timestamp': datetime.now().isoformat()
                        })
            
            print(f"[SCANNER] ARP scan found {len(devices)} devices")
            return devices
            
        except Exception as e:
            print(f"[SCANNER] ARP scan error: {e}")
            return []
    
    def scan_arp_table(self) -> List[Dict]:
        """Scan using system ARP table"""
        devices = []
        
        try:
            result = subprocess.run(
                ['arp', '-a'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse ARP table output
            pattern = r'(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]+)'
            
            for line in result.stdout.split('\n'):
                match = re.search(pattern, line)
                if match:
                    hostname, ip, mac = match.groups()
                    devices.append({
                        'ip': ip,
                        'mac': self._normalize_mac(mac),
                        'hostname': hostname,
                        'timestamp': datetime.now().isoformat()
                    })
            
            print(f"[SCANNER] ARP table found {len(devices)} devices")
            return devices
            
        except Exception as e:
            print(f"[SCANNER] ARP table error: {e}")
            return []
    
    def detect_presence(self) -> Tuple[List[str], List[str]]:
        """
        Detect which colleagues are present
        
        Returns:
            Tuple of (present_names, absent_names)
        """
        if not self.colleagues:
            print("[SCANNER] No colleagues configured")
            return [], []
        
        # Try arp-scan first, then ARP table
        devices = self.scan_with_arp()
        if not devices:
            devices = self.scan_arp_table()
        
        if not devices:
            print("[SCANNER] No devices found on network")
            return [], list(self.colleagues.keys())
        
        # Extract MACs from devices
        device_macs = {d['mac'] for d in devices if d.get('mac')}
        
        present = []
        absent = []
        
        for name, mac in self.colleagues.items():
            if mac in device_macs:
                present.append(name)
            else:
                absent.append(name)
        
        print(f"[SCANNER] Presence: {len(present)} present, {len(absent)} absent")
        return present, absent

# Test function
def test_scanner():
    """Test the scanner functionality"""
    print("🔍 Testing Network Scanner...")
    print("=" * 50)
    
    scanner = NetworkScanner()
    
    print(f"📋 Loaded {len(scanner.colleagues)} colleagues")
    
    print("\n🔄 Scanning network...")
    present, absent = scanner.detect_presence()
    
    print(f"\n✅ Results:")
    print(f"   Present: {len(present)}")
    for name in present:
        print(f"     👤 {name}")
    
    print(f"\n   Absent: {len(absent)}")
    for name in absent:
        print(f"     👤 {name}")
    
    print("\n✨ Test completed!")

if __name__ == "__main__":
    test_scanner()