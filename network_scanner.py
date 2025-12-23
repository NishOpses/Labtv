#!/usr/bin/env python3
"""
Office Presence Scanner
Scans network for MAC addresses to detect colleague presence
"""

import subprocess
import json
import re
import os
import logging
import threading
import time
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.devices_cache = []
        self.last_scan_time = None
        self.cache_duration = 300  # 5 minutes
        
        # Network settings
        self.network_range = self._detect_network_range()
        self.interface = self._detect_interface()
        
        logger.info(f"NetworkScanner initialized on {self.interface}, range: {self.network_range}")
    
    def _load_colleagues(self) -> Dict[str, str]:
        """Load colleagues from JSON file"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            colleagues_path = os.path.join(script_dir, self.config_file)
            
            if not os.path.exists(colleagues_path):
                logger.warning(f"Colleagues file not found: {colleagues_path}")
                return {}
            
            with open(colleagues_path, 'r') as f:
                colleagues = json.load(f)
            
            # Validate and normalize MAC addresses
            validated = {}
            for name, mac in colleagues.items():
                normalized = self._normalize_mac(mac)
                if normalized:
                    validated[name] = normalized
                else:
                    logger.warning(f"Invalid MAC for {name}: {mac}")
            
            logger.info(f"Loaded {len(validated)} colleagues")
            return validated
            
        except Exception as e:
            logger.error(f"Failed to load colleagues: {e}")
            return {}
    
    def _detect_network_range(self) -> str:
        """Detect the local network range"""
        try:
            # Get network info using ip command
            result = subprocess.run(
                ['ip', '-o', '-f', 'inet', 'addr', 'show'],
                capture_output=True, text=True
            )
            
            for line in result.stdout.split('\n'):
                if 'scope global' in line:
                    # Extract IP and subnet
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)/(\d+)', line)
                    if match:
                        ip, prefix = match.groups()
                        # Convert to CIDR notation
                        return f"{ip.split('.')[0]}.{ip.split('.')[1]}.{ip.split('.')[2]}.0/24"
            
            # Fallback to common ranges
            return "192.168.1.0/24"
            
        except Exception as e:
            logger.warning(f"Could not detect network range: {e}")
            return "192.168.1.0/24"
    
    def _detect_interface(self) -> str:
        """Detect the active network interface"""
        try:
            result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True, text=True
            )
            
            for line in result.stdout.split('\n'):
                if 'default via' in line:
                    match = re.search(r'dev\s+(\w+)', line)
                    if match:
                        return match.group(1)
            
            return "wlan0"
        except Exception as e:
            logger.warning(f"Could not detect interface: {e}")
            return "wlan0"
    
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
        """Scan using arp-scan (fastest method)"""
        devices = []
        
        try:
            # Check if arp-scan is installed
            check = subprocess.run(['which', 'arp-scan'], 
                                 capture_output=True, text=True)
            if not check.stdout.strip():
                logger.warning("arp-scan not installed")
                return devices
            
            # Run arp-scan
            cmd = [
                'sudo', 'arp-scan',
                '--localnet',
                '--interface', self.interface,
                '--retry=2',
                '--timeout=2000'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20
            )
            
            if result.returncode != 0:
                logger.warning(f"arp-scan failed: {result.stderr[:100]}")
                return devices
            
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
                            'vendor': parts[2].strip() if len(parts) > 2 else 'Unknown',
                            'timestamp': datetime.now().isoformat()
                        })
            
            logger.info(f"ARP scan found {len(devices)} devices")
            return devices
            
        except subprocess.TimeoutExpired:
            logger.error("ARP scan timed out")
            return devices
        except Exception as e:
            logger.error(f"ARP scan error: {e}")
            return devices
    
    def scan_with_nmap(self) -> List[Dict]:
        """Scan using nmap (more thorough)"""
        devices = []
        
        try:
            # Check if nmap is installed
            check = subprocess.run(['which', 'nmap'], 
                                 capture_output=True, text=True)
            if not check.stdout.strip():
                logger.warning("nmap not installed")
                return devices
            
            # Run nmap (no root needed for ping scan)
            cmd = [
                'nmap',
                '-sn',  # Ping scan only
                self.network_range,
                '--max-retries', '1',
                '--max-rtt-timeout', '300ms',
                '--host-timeout', '3s'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse nmap output
            current_ip = None
            for line in result.stdout.split('\n'):
                # Extract IP
                ip_match = re.search(r'Nmap scan report for ([\d\.]+)', line)
                if ip_match:
                    current_ip = ip_match.group(1)
                
                # Extract MAC
                mac_match = re.search(r'MAC Address: ([\w:]+)', line, re.IGNORECASE)
                if mac_match and current_ip:
                    devices.append({
                        'ip': current_ip,
                        'mac': self._normalize_mac(mac_match.group(1)),
                        'vendor': line.split('(')[-1].rstrip(')') if '(' in line else 'Unknown',
                        'timestamp': datetime.now().isoformat()
                    })
            
            logger.info(f"Nmap scan found {len(devices)} devices")
            return devices
            
        except subprocess.TimeoutExpired:
            logger.error("Nmap scan timed out")
            return devices
        except Exception as e:
            logger.error(f"Nmap scan error: {e}")
            return devices
    
    def get_all_devices(self, use_cache: bool = True) -> List[Dict]:
        """
        Get all devices on network, using cache if recent
        
        Args:
            use_cache: Use cached results if available and fresh
        
        Returns:
            List of device dictionaries
        """
        # Check cache
        if use_cache and self.devices_cache and self.last_scan_time:
            cache_age = (datetime.now() - self.last_scan_time).total_seconds()
            
            if cache_age < self.cache_duration:
                logger.debug(f"Using cached device list ({len(self.devices_cache)} devices)")
                return self.devices_cache
        
        # Try multiple scanning methods
        devices = []
        
        # Method 1: arp-scan (fastest)
        devices = self.scan_with_arp()
        
        # Method 2: nmap (if arp-scan found nothing)
        if not devices:
            devices = self.scan_with_nmap()
        
        # Method 3: arp table (fallback)
        if not devices:
            devices = self._scan_arp_table()
        
        # Update cache
        self.devices_cache = devices
        self.last_scan_time = datetime.now()
        
        return devices
    
    def _scan_arp_table(self) -> List[Dict]:
        """Fallback scan using system ARP table"""
        devices = []
        
        try:
            result = subprocess.run(
                ['arp', '-a'],
                capture_output=True,
                text=True
            )
            
            # Parse ARP table output
            for line in result.stdout.split('\n'):
                # Match patterns like "raspberrypi (192.168.1.1) at aa:bb:cc:dd:ee:ff"
                patterns = [
                    r'(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]+)',
                    r'(\d+\.\d+\.\d+\.\d+)\s+ether\s+([0-9a-fA-F:]+)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        if len(match.groups()) == 3:
                            hostname, ip, mac = match.groups()
                        else:
                            ip, mac = match.groups()
                            hostname = "Unknown"
                        
                        devices.append({
                            'ip': ip,
                            'mac': self._normalize_mac(mac),
                            'hostname': hostname,
                            'timestamp': datetime.now().isoformat()
                        })
                        break
            
            logger.info(f"ARP table scan found {len(devices)} devices")
            return devices
            
        except Exception as e:
            logger.error(f"ARP table scan error: {e}")
            return []
    
    def detect_presence(self) -> Tuple[List[str], List[str]]:
        """
        Detect which colleagues are present
        
        Returns:
            Tuple of (present_names, absent_names)
        """
        # Clear cache for fresh scan
        self.devices_cache = []
        
        devices = self.get_all_devices(use_cache=False)
        
        if not self.colleagues:
            logger.warning("No colleagues configured")
            return [], []
        
        if not devices:
            logger.warning("No devices found on network")
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
        
        logger.info(f"Presence: {len(present)} present, {len(absent)} absent")
        return present, absent
    
    def get_detailed_presence(self) -> Dict:
        """
        Get detailed presence information
        
        Returns:
            Dictionary with present/absent lists and device info
        """
        devices = self.get_all_devices(use_cache=False)
        present_names, absent_names = self.detect_presence()
        
        # Get detailed info for present colleagues
        present_details = []
        for name in present_names:
            mac = self.colleagues.get(name)
            if mac:
                # Find the device info
                device_info = next((d for d in devices if d.get('mac') == mac), {})
                present_details.append({
                    'name': name,
                    'mac': mac,
                    'ip': device_info.get('ip', 'Unknown'),
                    'last_seen': device_info.get('timestamp', 'Unknown'),
                    'device': device_info.get('vendor', 'Unknown')
                })
        
        return {
            'present': present_details,
            'absent': absent_names,
            'total_devices': len(devices),
            'last_scan': datetime.now().isoformat()
        }

# Test function
def test_scanner():
    """Test the scanner functionality"""
    print("🔍 Testing Network Scanner...")
    print("=" * 50)
    
    scanner = NetworkScanner()
    
    print(f"📋 Loaded {len(scanner.colleagues)} colleagues")
    print(f"🌐 Network: {scanner.network_range} on {scanner.interface}")
    
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