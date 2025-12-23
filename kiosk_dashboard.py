#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import io
import platform
import qrcode
import psutil
import threading
import time
import subprocess
import requests
import json
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template_string, send_file, request, jsonify

# Try to import required modules with fallbacks
try:
    from useful_info import get_time_info
except ImportError:
    print("[WARNING] useful_info module not found. Using fallback date function.")
    def get_time_info():
        return {"date": datetime.now().strftime("%A, %d %B %Y")}

try:
    from ics import Calendar
    ics_available = True
except ImportError:
    print("[WARNING] ics module not available. Calendar functionality disabled.")
    ics_available = False

# =====================
# Network Scanner Integration
# =====================
try:
    from network_scanner import NetworkScanner
    NETWORK_SCANNER_AVAILABLE = True
    print("[DEBUG] Network scanner module loaded successfully")
    network_scanner = NetworkScanner()
except ImportError as e:
    print(f"[WARNING] Network scanner module not available: {e}")
    print("[WARNING] Falling back to basic ARP table detection")
    NETWORK_SCANNER_AVAILABLE = False

# Fallback functions
def get_present_absent_colleagues_fallback():
    """Fallback function using old ARP table method"""
    try:
        colleagues_file = os.path.join(os.path.dirname(__file__), "colleagues.json")
        if not os.path.exists(colleagues_file):
            print("[DEBUG] Colleagues file not found")
            return [], []
        
        with open(colleagues_file, "r", encoding="utf-8") as f:
            colleagues = json.load(f)
        
        # Get ARP table
        if platform.system().lower() == "windows":
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        else:
            output = subprocess.check_output(["arp", "-a"], encoding="utf-8", stderr=subprocess.DEVNULL)
        
        present = []
        absent = []
        
        for name, mac in colleagues.items():
            if mac and mac.lower() in output.lower():
                present.append(name)
            else:
                absent.append(name)
                
        print(f"[DEBUG] Fallback: Present: {len(present)}, Absent: {len(absent)}")
        return present, absent
        
    except Exception as e:
        print(f"[DEBUG] Fallback detection error: {e}")
        return [], []

def get_present_absent_colleagues():
    """Get presence using new scanner or fallback"""
    if NETWORK_SCANNER_AVAILABLE:
        try:
            present, absent = network_scanner.detect_presence()
            print(f"[DEBUG] Scanner: Present: {len(present)}, Absent: {len(absent)}")
            return present, absent
        except Exception as e:
            print(f"[ERROR] Scanner failed: {e}")
            return get_present_absent_colleagues_fallback()
    else:
        return get_present_absent_colleagues_fallback()

# =====================
# Calendar Feed Config
# =====================
OUTLOOK_ICAL_URL = os.environ.get("OUTLOOK_ICAL_URL", "https://outlook.office365.com/owa/calendar/744e18cdc1534f5dbcdf3283c76a8f8b@opses.co.uk/85260d62ab584bd69aca5ac9a4223dd84268036899588616720/calendar.ics")
CALENDAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_cache.json")
CALENDAR_CACHE_MINUTES = 15

def get_calendar_events():
    if not ics_available:
        print("[DEBUG] ICS module not available, returning empty calendar events")
        return []
    
    print("[DEBUG] get_calendar_events: Called")
    if not OUTLOOK_ICAL_URL or OUTLOOK_ICAL_URL == "":
        print("[DEBUG] No OUTLOOK_ICAL_URL set")
        return []
    
    try:
        import pytz
        utc = pytz.UTC
        now = datetime.utcnow().replace(tzinfo=utc)
        
        # Try cache
        if os.path.exists(CALENDAR_CACHE_FILE):
            try:
                with open(CALENDAR_CACHE_FILE, "r") as f:
                    data = json.load(f)
                ts = datetime.fromisoformat(data.get("timestamp"))
                if (now - ts) < timedelta(minutes=CALENDAR_CACHE_MINUTES):
                    print(f"[DEBUG] Using cached calendar events: {len(data['events'])} events")
                    return data["events"]
            except Exception as e:
                print(f"[DEBUG] Error reading calendar cache: {e}")
        
        # Fetch from iCal feed
        print(f"[DEBUG] Fetching ICS feed: {OUTLOOK_ICAL_URL}")
        resp = requests.get(OUTLOOK_ICAL_URL, timeout=10)
        print(f"[DEBUG] ICS HTTP status: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                c = Calendar(resp.text)
                events = []
                for e in sorted(c.timeline, key=lambda ev: ev.begin):
                    # Ensure event datetime is offset-aware (UTC)
                    event_dt = e.begin.datetime
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=utc)
                    else:
                        event_dt = event_dt.astimezone(utc)
                    
                    # Only show future events (today and next 7 days)
                    if event_dt >= now and event_dt <= now + timedelta(days=7):
                        events.append({
                            "start": event_dt.strftime('%Y-%m-%d %H:%M'),
                            "summary": e.name or "(No Title)",
                            "location": getattr(e, 'location', None) or ""
                        })
                        if len(events) >= 5:
                            break
                
                print(f"[DEBUG] Parsed {len(events)} upcoming events from ICS feed")
                
                # Save to cache
                try:
                    with open(CALENDAR_CACHE_FILE, "w") as f:
                        json.dump({"timestamp": now.isoformat(), "events": events}, f)
                except Exception as e:
                    print(f"[DEBUG] Error saving calendar cache: {e}")
                
                return events
            except Exception as e:
                print(f"[DEBUG] Error parsing ICS feed: {e}")
                return []
        else:
            print(f"[DEBUG] ICS feed fetch failed with status {resp.status_code}")
            return []
    except Exception as e:
        print(f"[DEBUG] Exception fetching/parsing ICS feed: {e}")
        return []
    
    return []

# =====================
# App setup
# =====================
app = Flask(__name__)

WIFI_SSID = os.environ.get("WIFI_SSID", "Opses_Global_Guest")
WIFI_PASSWORD = os.environ.get("WIFI_PASSWORD", "Covert3791Beer105%")
WIFI_AUTH = os.environ.get("WIFI_AUTH", "WPA")

# =====================
# Background updater
# =====================
UPDATE_CHECK_INTERVAL = 3600
UPDATE_COMMAND = os.environ.get("KIOSK_UPDATE_COMMAND", "git pull")
LAST_UPDATE_FILE = os.path.join(os.path.dirname(__file__), "last_update.txt")

def background_update_loop():
    while True:
        try:
            print("[DEBUG] Running background update check...")
            result = subprocess.run(
                UPDATE_COMMAND,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            with open(LAST_UPDATE_FILE, "w") as f:
                f.write(f"Last checked: {datetime.now().isoformat()}\n")
                f.write(f"Command: {UPDATE_COMMAND}\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"Output:\n{result.stdout}\nErrors:\n{result.stderr}\n")
            print(f"[DEBUG] Update check completed. Return code: {result.returncode}")
        except Exception as e:
            print(f"[DEBUG] Update error: {e}")
            try:
                with open(LAST_UPDATE_FILE, "a") as f:
                    f.write(f"Update error at {datetime.now().isoformat()}: {e}\n")
            except:
                pass
        time.sleep(UPDATE_CHECK_INTERVAL)

# =====================
# Enhanced HTML Template with Modern UI
# =====================
TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Opses Lab Dashboard</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #2ecc40;
            --secondary: #3498db;
            --accent: #9b59b6;
            --dark: #0a0e14;
            --darker: #1a1f29;
            --light: #ffffff;
            --gray: #b0b7c3;
            --success: #2ecc40;
            --warning: #f39c12;
            --danger: #e74c3c;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', 'Roboto', Arial, sans-serif;
            margin: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, var(--dark) 0%, var(--darker) 100%);
            color: var(--light);
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-x: hidden;
            position: relative;
        }
        
        /* Main content container */
        .main-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            max-width: 1200px;
            padding: 20px;
            gap: 20px;
            margin-top: 10px;
            overflow-y: auto;
            height: 100vh;
        }
        
        /* Header section */
        .header-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            margin-bottom: 10px;
        }
        
        .company-logo {
            width: 200px;
            background: var(--light);
            border-radius: 20px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border: 3px solid var(--primary);
        }
        
        /* Time section */
        .time-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(24, 28, 32, 0.9);
            border-radius: 25px;
            padding: 25px 40px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
            width: 95%;
            max-width: 1000px;
            margin-bottom: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(46, 204, 64, 0.2);
        }
        
        .public-clock {
            font-size: 120px;
            color: var(--light);
            font-weight: 800;
            letter-spacing: 5px;
            text-shadow: 0 5px 20px rgba(0,0,0,0.8);
            font-family: 'Courier New', monospace;
            line-height: 1;
            margin: 10px 0;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .clock-colon {
            animation: blink 1.5s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .public-date {
            font-size: 28px;
            color: var(--gray);
            font-weight: 500;
            text-align: center;
            margin-top: 10px;
            letter-spacing: 1px;
        }
        
        /* Info panels grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
            margin: 10px 0;
        }
        
        .card {
            background: rgba(24, 28, 32, 0.9);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s, box-shadow 0.3s;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.4);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--primary);
        }
        
        .card-icon {
            font-size: 28px;
            margin-right: 15px;
            color: var(--primary);
        }
        
        .card-title {
            font-size: 26px;
            color: var(--primary);
            font-weight: 700;
        }
        
        /* Weather card */
        .weather-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-grow: 1;
        }
        
        .weather-main {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            margin-bottom: 15px;
        }
        
        .weather-icon {
            width: 100px;
            height: 100px;
        }
        
        .weather-temp {
            font-size: 72px;
            font-weight: 800;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .weather-desc {
            font-size: 22px;
            color: var(--gray);
            text-align: center;
            margin-bottom: 10px;
        }
        
        /* Calendar card */
        .calendar-list {
            list-style: none;
            padding: 0;
            margin: 0;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 250px;
        }
        
        .calendar-list::-webkit-scrollbar {
            width: 6px;
        }
        
        .calendar-list::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }
        
        .calendar-list::-webkit-scrollbar-thumb {
            background: var(--primary);
            border-radius: 3px;
        }
        
        .calendar-item {
            padding: 15px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
        }
        
        .event-time {
            color: var(--primary);
            font-weight: 700;
            font-size: 18px;
            margin-bottom: 5px;
        }
        
        .event-title {
            color: var(--light);
            font-size: 20px;
            margin-bottom: 5px;
        }
        
        .event-location {
            color: var(--gray);
            font-size: 16px;
            font-style: italic;
        }
        
        .no-events {
            color: var(--gray);
            font-size: 20px;
            text-align: center;
            padding: 30px 0;
            font-style: italic;
        }
        
        /* Presence card */
        .presence-card {
            grid-column: span 2;
        }
        
        .presence-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .stat-box {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stat-value {
            font-size: 48px;
            font-weight: 800;
            margin-bottom: 5px;
        }
        
        .stat-present .stat-value { color: var(--success); }
        .stat-absent .stat-value { color: var(--gray); }
        .stat-total .stat-value { color: var(--secondary); }
        
        .stat-label {
            font-size: 18px;
            color: var(--gray);
            font-weight: 600;
        }
        
        .presence-lists {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-top: 10px;
        }
        
        .presence-column {
            display: flex;
            flex-direction: column;
        }
        
        .column-title {
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid;
        }
        
        .present-title { color: var(--success); border-color: var(--success); }
        .absent-title { color: var(--gray); border-color: var(--gray); }
        
        .presence-list {
            list-style: none;
            padding: 0;
            margin: 0;
            flex-grow: 1;
        }
        
        .presence-item {
            padding: 15px;
            margin-bottom: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            display: flex;
            align-items: center;
            transition: background 0.3s;
        }
        
        .presence-item:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .presence-badge {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 15px;
        }
        
        .present-badge {
            background-color: var(--success);
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }
        
        .absent-badge {
            background-color: var(--gray);
        }
        
        .person-name {
            font-size: 20px;
            font-weight: 600;
            flex-grow: 1;
        }
        
        .person-status {
            font-size: 14px;
            padding: 5px 10px;
            border-radius: 20px;
            font-weight: 600;
        }
        
        .status-present {
            background: rgba(46, 204, 64, 0.2);
            color: var(--success);
        }
        
        .status-absent {
            background: rgba(176, 183, 195, 0.2);
            color: var(--gray);
        }
        
        /* System info bar */
        .system-info-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: rgba(10, 14, 20, 0.95);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 2px solid var(--primary);
            z-index: 1000;
            backdrop-filter: blur(15px);
            box-shadow: 0 -5px 20px rgba(0,0,0,0.3);
        }
        
        .system-stats {
            display: flex;
            gap: 40px;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .stat-icon {
            font-size: 20px;
        }
        
        .cpu-icon { color: var(--success); }
        .mem-icon { color: var(--secondary); }
        .disk-icon { color: var(--accent); }
        
        .stat-label-small {
            font-size: 16px;
            color: var(--gray);
            font-weight: 600;
        }
        
        .stat-value-small {
            font-size: 22px;
            color: var(--light);
            font-weight: 700;
            min-width: 60px;
        }
        
        .wifi-section {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .wifi-info {
            text-align: right;
        }
        
        .wifi-ssid {
            font-size: 20px;
            color: var(--light);
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .wifi-instruction {
            font-size: 14px;
            color: var(--gray);
        }
        
        .wifi-qr-small {
            width: 80px;
            background: var(--light);
            border-radius: 10px;
            padding: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            border: 2px solid var(--primary);
        }
        
        /* Refresh button */
        .refresh-button {
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 5px 15px rgba(46, 204, 64, 0.4);
            z-index: 1001;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .refresh-button:hover {
            transform: rotate(180deg);
            box-shadow: 0 8px 20px rgba(46, 204, 64, 0.6);
        }
        
        /* Last scan info */
        .last-scan {
            text-align: center;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--gray);
            font-size: 16px;
        }
        
        .scan-time {
            color: var(--secondary);
            font-weight: 600;
        }
        
        /* Responsive */
        @media (max-width: 1200px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
            
            .presence-card {
                grid-column: span 1;
            }
            
            .presence-lists {
                grid-template-columns: 1fr;
                gap: 20px;
            }
            
            .public-clock {
                font-size: 80px;
            }
        }
        
        @media (max-width: 768px) {
            .main-container {
                padding: 10px;
            }
            
            .public-clock {
                font-size: 60px;
            }
            
            .public-date {
                font-size: 20px;
            }
            
            .card-title {
                font-size: 22px;
            }
            
            .weather-temp {
                font-size: 50px;
            }
            
            .system-stats {
                gap: 20px;
            }
            
            .stat-value-small {
                font-size: 18px;
            }
        }
        
        /* Animations */
        @keyframes pulse {
            0% { opacity: 0.6; box-shadow: 0 0 5px var(--success); }
            50% { opacity: 1; box-shadow: 0 0 15px var(--success); }
            100% { opacity: 0.6; box-shadow: 0 0 5px var(--success); }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .card {
            animation: fadeIn 0.5s ease-out;
        }
    </style>
</head>
<body>
    <!-- Refresh Button -->
    <button class="refresh-button" onclick="refreshPresence()">
        <i class="fas fa-sync-alt"></i>
    </button>
    
    <div class="main-container">
        <!-- Header with logo -->
        <div class="header-section">
            <img class="company-logo" src="/static/Opses_Logo.jpg" alt="Opses Logo" onerror="this.style.display='none'">
        </div>
        
        <!-- Time section -->
        <div class="time-section">
            <div class="public-clock" id="publicclock">
                <span id="clock-hour">00</span><span class="clock-colon">:</span><span id="clock-minute">00</span><span class="clock-colon">:</span><span id="clock-second">00</span>
            </div>
            <div class="public-date">{{ date }}</div>
        </div>
        
        <!-- Dashboard Grid -->
        <div class="dashboard-grid">
            <!-- Weather Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-cloud-sun card-icon"></i>
                    <div class="card-title">Weather</div>
                </div>
                <div class="weather-content">
                    {% if weather and weather.temp is defined %}
                    <div class="weather-main">
                        <img class="weather-icon" src="{{ weather.icon_url }}" alt="{{ weather.desc }}" onerror="this.style.display='none'">
                        <div class="weather-temp">{{ weather.temp }}°C</div>
                    </div>
                    <div class="weather-desc">{{ weather.desc }}</div>
                    {% else %}
                    <div class="weather-desc" style="font-size: 22px; padding: 30px 0; text-align: center;">
                        <i class="fas fa-cloud-slash" style="font-size: 48px; margin-bottom: 15px; display: block; color: var(--gray);"></i>
                        Weather data unavailable
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <!-- Calendar Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-calendar-alt card-icon"></i>
                    <div class="card-title">Upcoming Events</div>
                </div>
                <div class="calendar-content">
                    {% if calendar_events and calendar_events|length > 0 %}
                    <ul class="calendar-list">
                        {% for event in calendar_events %}
                        <li class="calendar-item">
                            <div class="event-time">
                                <i class="far fa-clock"></i> {{ event.start[5:16] if event.start|length > 16 else event.start }}
                            </div>
                            <div class="event-title">{{ event.summary }}</div>
                            {% if event.location and event.location|length > 0 %}
                            <div class="event-location">
                                <i class="fas fa-map-marker-alt"></i> {{ event.location }}
                            </div>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                    {% else %}
                    <div class="no-events">
                        <i class="far fa-calendar-times" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
                        No upcoming events
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <!-- Presence Card -->
            <div class="card presence-card">
                <div class="card-header">
                    <i class="fas fa-users card-icon"></i>
                    <div class="card-title">Office Presence</div>
                </div>
                
                <!-- Stats -->
                <div class="presence-stats">
                    <div class="stat-box stat-present">
                        <div class="stat-value" id="present-count">{{ present_colleagues|length }}</div>
                        <div class="stat-label">Present</div>
                    </div>
                    <div class="stat-box stat-absent">
                        <div class="stat-value" id="absent-count">{{ absent_colleagues|length }}</div>
                        <div class="stat-label">Absent</div>
                    </div>
                    <div class="stat-box stat-total">
                        <div class="stat-value" id="total-count">{{ present_colleagues|length + absent_colleagues|length }}</div>
                        <div class="stat-label">Total</div>
                    </div>
                </div>
                
                <!-- Presence Lists -->
                <div class="presence-lists">
                    <!-- Present Column -->
                    <div class="presence-column">
                        <div class="column-title present-title">
                            <i class="fas fa-check-circle"></i> In Office
                        </div>
                        <ul class="presence-list" id="present-list">
                            {% if present_colleagues and present_colleagues|length > 0 %}
                                {% for person in present_colleagues %}
                                <li class="presence-item">
                                    <div class="presence-badge present-badge"></div>
                                    <div class="person-name">{{ person }}</div>
                                    <div class="person-status status-present">Connected</div>
                                </li>
                                {% endfor %}
                            {% else %}
                                <li class="presence-item" style="justify-content: center; text-align: center;">
                                    <div class="person-name" style="color: var(--gray); font-style: italic;">
                                        <i class="fas fa-user-slash" style="margin-right: 10px;"></i>
                                        No one in office
                                    </div>
                                </li>
                            {% endif %}
                        </ul>
                    </div>
                    
                    <!-- Absent Column -->
                    <div class="presence-column">
                        <div class="column-title absent-title">
                            <i class="fas fa-times-circle"></i> Out of Office
                        </div>
                        <ul class="presence-list" id="absent-list">
                            {% if absent_colleagues and absent_colleagues|length > 0 %}
                                {% for person in absent_colleagues %}
                                <li class="presence-item">
                                    <div class="presence-badge absent-badge"></div>
                                    <div class="person-name">{{ person }}</div>
                                    <div class="person-status status-absent">Away</div>
                                </li>
                                {% endfor %}
                            {% else %}
                                <li class="presence-item" style="justify-content: center; text-align: center;">
                                    <div class="person-name" style="color: var(--success); font-style: italic;">
                                        <i class="fas fa-user-check" style="margin-right: 10px;"></i>
                                        Everyone is here!
                                    </div>
                                </li>
                            {% endif %}
                        </ul>
                    </div>
                </div>
                
                <!-- Last scan info -->
                <div class="last-scan">
                    <i class="fas fa-clock"></i> Last scanned: 
                    <span class="scan-time" id="last-scan-time">Just now</span>
                    • Auto-refresh: <span id="refresh-countdown">30</span>s
                </div>
            </div>
        </div>
    </div>
    
    <!-- System info bar at bottom -->
    <div class="system-info-bar">
        <div class="system-stats">
            <div class="stat-item">
                <i class="fas fa-microchip cpu-icon stat-icon"></i>
                <span class="stat-label-small">CPU:</span>
                <span class="stat-value-small cpu-value">{{ sys_status.cpu }}%</span>
            </div>
            <div class="stat-item">
                <i class="fas fa-memory mem-icon stat-icon"></i>
                <span class="stat-label-small">RAM:</span>
                <span class="stat-value-small mem-value">{{ sys_status.mem }}%</span>
            </div>
            <div class="stat-item">
                <i class="fas fa-hdd disk-icon stat-icon"></i>
                <span class="stat-label-small">Disk:</span>
                <span class="stat-value-small disk-value">{{ sys_status.disk }}%</span>
            </div>
        </div>
        
        <div class="wifi-section">
            <div class="wifi-info">
                <div class="wifi-ssid">{{ ssid }}</div>
                <div class="wifi-instruction">Scan QR to connect</div>
            </div>
            <img class="wifi-qr-small" src="/wifi_qr" alt="WiFi QR Code">
        </div>
    </div>
    
    <script>
        // Update clock
        function pad(n) { return n.toString().padStart(2, '0'); }
        
        function updateClock() {
            try {
                const now = new Date();
                document.getElementById('clock-hour').textContent = pad(now.getHours());
                document.getElementById('clock-minute').textContent = pad(now.getMinutes());
                document.getElementById('clock-second').textContent = pad(now.getSeconds());
            } catch (e) {
                console.error('Clock update error:', e);
            }
        }
        
        updateClock();
        setInterval(updateClock, 1000);
        
        // Refresh presence data
        let refreshCountdown = 30;
        let countdownInterval;
        
        function startCountdown() {
            refreshCountdown = 30;
            clearInterval(countdownInterval);
            
            countdownInterval = setInterval(() => {
                refreshCountdown--;
                document.getElementById('refresh-countdown').textContent = refreshCountdown;
                
                if (refreshCountdown <= 0) {
                    refreshPresence();
                }
            }, 1000);
        }
        
        function refreshPresence() {
            // Show loading state
            const refreshBtn = document.querySelector('.refresh-button');
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            refreshBtn.style.pointerEvents = 'none';
            
            fetch('/api/presence')
                .then(response => response.json())
                .then(data => {
                    // Update present list
                    const presentList = document.getElementById('present-list');
                    const absentList = document.getElementById('absent-list');
                    
                    // Clear current lists
                    presentList.innerHTML = '';
                    absentList.innerHTML = '';
                    
                    // Update present
                    if (data.present && data.present.length > 0) {
                        data.present.forEach(person => {
                            const li = document.createElement('li');
                            li.className = 'presence-item';
                            li.innerHTML = `
                                <div class="presence-badge present-badge"></div>
                                <div class="person-name">${person}</div>
                                <div class="person-status status-present">Connected</div>
                            `;
                            presentList.appendChild(li);
                        });
                    } else {
                        const li = document.createElement('li');
                        li.className = 'presence-item';
                        li.style.justifyContent = 'center';
                        li.style.textAlign = 'center';
                        li.innerHTML = `
                            <div class="person-name" style="color: #b0b7c3; font-style: italic;">
                                <i class="fas fa-user-slash" style="margin-right: 10px;"></i>
                                No one in office
                            </div>
                        `;
                        presentList.appendChild(li);
                    }
                    
                    // Update absent
                    if (data.absent && data.absent.length > 0) {
                        data.absent.forEach(person => {
                            const li = document.createElement('li');
                            li.className = 'presence-item';
                            li.innerHTML = `
                                <div class="presence-badge absent-badge"></div>
                                <div class="person-name">${person}</div>
                                <div class="person-status status-absent">Away</div>
                            `;
                            absentList.appendChild(li);
                        });
                    } else {
                        const li = document.createElement('li');
                        li.className = 'presence-item';
                        li.style.justifyContent = 'center';
                        li.style.textAlign = 'center';
                        li.innerHTML = `
                            <div class="person-name" style="color: #2ecc40; font-style: italic;">
                                <i class="fas fa-user-check" style="margin-right: 10px;"></i>
                                Everyone is here!
                            </div>
                        `;
                        absentList.appendChild(li);
                    }
                    
                    // Update counts
                    document.getElementById('present-count').textContent = data.present.length;
                    document.getElementById('absent-count').textContent = data.absent.length;
                    document.getElementById('total-count').textContent = data.present.length + data.absent.length;
                    
                    // Update last scan time
                    const now = new Date();
                    document.getElementById('last-scan-time').textContent = 
                        now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    // Reset button
                    refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
                    refreshBtn.style.pointerEvents = 'auto';
                    
                    // Restart countdown
                    startCountdown();
                })
                .catch(error => {
                    console.error('Error refreshing presence:', error);
                    refreshBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
                    setTimeout(() => {
                        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
                        refreshBtn.style.pointerEvents = 'auto';
                    }, 2000);
                });
        }
        
        // Start countdown on page load
        startCountdown();
        
        // Auto-refresh presence when page becomes visible
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) {
                refreshPresence();
            }
        });
        
        // Initialize with fade-in animation
        document.addEventListener('DOMContentLoaded', function() {
            // Add animation to cards
            const cards = document.querySelectorAll('.card');
            cards.forEach((card, index) => {
                card.style.animationDelay = `${index * 0.1}s`;
            });
        });
    </script>
</body>
</html>"""

# =====================
# Routes
# =====================
@app.route("/wifi_qr")
def wifi_qr():
    try:
        qr_str = f"WIFI:T:{WIFI_AUTH};S:{WIFI_SSID};P:{WIFI_PASSWORD};;"
        img = qrcode.make(qr_str)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        print(f"[ERROR] Failed to generate WiFi QR: {e}")
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (150, 150), color='white')
        d = ImageDraw.Draw(img)
        d.text((75, 75), "QR Error", fill='black', anchor='mm')
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

WEATHER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "weather_cache.json")
WEATHER_API_KEY = "144536c74a836feb69c1cd449b8457b9"
WEATHER_LAT = 51.0902
WEATHER_LON = -1.1662
WEATHER_CACHE_MINUTES = 15

def get_weather():
    try:
        now = datetime.utcnow()

        # Try cache
        if os.path.exists(WEATHER_CACHE_FILE):
            try:
                with open(WEATHER_CACHE_FILE) as f:
                    data = json.load(f)
                ts = datetime.fromisoformat(data["timestamp"])
                if (now - ts) < timedelta(minutes=WEATHER_CACHE_MINUTES):
                    print(f"[DEBUG] Using cached weather data")
                    return data["weather"]
            except Exception as e:
                print(f"[DEBUG] Error reading weather cache: {e}")

        # Fetch from API
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={WEATHER_LAT}&lon={WEATHER_LON}"
                f"&appid={WEATHER_API_KEY}&units=metric"
            )
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                w = r.json()
                icon = w['weather'][0]['icon']
                desc = w['weather'][0]['description'].lower()
                if 'rain' in desc or 'drizzle' in desc:
                    weather_class = 'rainy'
                elif 'snow' in desc:
                    weather_class = 'snowy'
                elif 'cloud' in desc or icon.startswith('03') or icon.startswith('04'):
                    weather_class = 'cloudy'
                elif 'clear' in desc or icon.startswith('01'):
                    weather_class = 'sunny'
                elif 'thunder' in desc:
                    weather_class = 'stormy'
                elif 'mist' in desc or 'fog' in desc or 'haze' in desc:
                    weather_class = 'foggy'
                else:
                    weather_class = 'default'
                weather = {
                    "temp": int(round(w["main"]["temp"])),
                    "desc": w["weather"][0]["description"].title(),
                    "icon_url": f"https://openweathermap.org/img/wn/{w['weather'][0]['icon']}@4x.png",
                    "weather_class": weather_class
                }
                try:
                    with open(WEATHER_CACHE_FILE, "w") as f:
                        json.dump({"timestamp": now.isoformat(), "weather": weather}, f)
                except Exception as e:
                    print(f"[DEBUG] Error saving weather cache: {e}")
                return weather
            else:
                print(f"[DEBUG] Weather API failed with status {r.status_code}")
                return None
        except Exception as e:
            print(f"[DEBUG] Exception fetching weather: {e}")
            return None
    except Exception as e:
        print(f"[ERROR] Unexpected error in get_weather: {e}")
        return None

def get_system_status():
    try:
        return {
            "cpu": round(psutil.cpu_percent(interval=0.5), 1),
            "mem": round(psutil.virtual_memory().percent, 1),
            "disk": round(psutil.disk_usage("/").percent, 1)
        }
    except Exception as e:
        print(f"[ERROR] Failed to get system status: {e}")
        return {"cpu": 0, "mem": 0, "disk": 0}

@app.route("/api/presence")
def api_presence():
    """API endpoint for presence data"""
    try:
        present, absent = get_present_absent_colleagues()
        return jsonify({
            "present": present,
            "absent": absent,
            "timestamp": datetime.now().isoformat(),
            "total": len(present) + len(absent)
        })
    except Exception as e:
        print(f"[ERROR] API presence error: {e}")
        return jsonify({
            "present": [],
            "absent": [],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

@app.route("/")
def public_info():
    try:
        print(f"[DEBUG] Handling request")
        
        # Get all data with error handling
        weather = None
        try:
            weather = get_weather()
        except Exception as e:
            print(f"[ERROR] Weather fetch failed: {e}")
        
        present_colleagues = []
        absent_colleagues = []
        try:
            present_colleagues, absent_colleagues = get_present_absent_colleagues()
        except Exception as e:
            print(f"[ERROR] Colleagues detection failed: {e}")
        
        calendar_events = []
        try:
            calendar_events = get_calendar_events()
        except Exception as e:
            print(f"[ERROR] Calendar events fetch failed: {e}")
        
        sys_status = {}
        try:
            sys_status = get_system_status()
        except Exception as e:
            print(f"[ERROR] System status fetch failed: {e}")
            sys_status = {"cpu": 0, "mem": 0, "disk": 0}
        
        # Get date safely
        date_str = "Loading..."
        try:
            date_info = get_time_info()
            date_str = date_info.get("date", datetime.now().strftime("%A, %d %B %Y"))
        except Exception as e:
            print(f"[ERROR] Date fetch failed: {e}")
            date_str = datetime.now().strftime("%A, %d %B %Y")
        
        # Render template
        return render_template_string(
            TEMPLATE,
            date=date_str,
            weather=weather,
            sys_status=sys_status,
            ssid=WIFI_SSID,
            calendar_events=calendar_events,
            present_colleagues=present_colleagues,
            absent_colleagues=absent_colleagues
        )
        
    except Exception as e:
        print(f"[CRITICAL] Unhandled exception in public_info: {e}")
        print(traceback.format_exc())
        return """
        <html>
        <head><title>Opses Dashboard - Error</title></head>
        <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
            <div style="text-align: center; padding: 20px;">
                <h1>Opses Lab Dashboard</h1>
                <p style="color: #ff4136;">Temporary error loading dashboard</p>
                <p>Please try refreshing the page.</p>
                <p><small>Error: """ + str(e)[:100] + """</small></p>
            </div>
        </body>
        </html>
        """, 500

@app.errorhandler(404)
def page_not_found(e):
    return """
    <html>
    <head><title>Page Not Found</title></head>
    <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
        <div style="text-align: center;">
            <h1>404 - Page Not Found</h1>
            <p><a href="/" style="color: #2ecc40;">Return to Dashboard</a></p>
        </div>
    </body>
    </html>
    """, 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"[CRITICAL] 500 Error: {e}")
    return """
    <html>
    <head><title>Server Error</title></head>
    <body style="background: #101217; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0;">
        <div style="text-align: center; padding: 20px;">
            <h1>500 - Internal Server Error</h1>
            <p>The dashboard encountered an error.</p>
            <p><a href="/" style="color: #2ecc40;">Try Again</a></p>
        </div>
    </body>
    </html>
    """, 500

# =====================
# Main
# =====================
if __name__ == "__main__":
    print("=" * 60)
    print("Opses Lab Dashboard Starting...")
    print(f"Running on Raspberry Pi: {platform.system()}")
    print(f"Python version: {platform.python_version()}")
    print(f"Server will be available at: http://0.0.0.0:8081")
    print(f"Network Scanner Available: {NETWORK_SCANNER_AVAILABLE}")
    print("=" * 60)
    
    # Start background update thread
    try:
        update_thread = threading.Thread(target=background_update_loop, daemon=True)
        update_thread.start()
        print("[DEBUG] Background update thread started")
    except Exception as e:
        print(f"[WARNING] Failed to start background update thread: {e}")
    
    # Run the Flask app
    try:
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        app.run(host="0.0.0.0", port=8081, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"[CRITICAL] Failed to start Flask server: {e}")
        print(traceback.format_exc())