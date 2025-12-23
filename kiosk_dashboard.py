# Replace your TEMPLATE variable with this optimized version:

TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Opses Lab Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #0a0e14 0%, #1a1f29 100%);
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-x: hidden;
            position: relative;
        }
        
        /* Main content container - optimized for vertical flow */
        .main-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            max-width: 1000px;
            padding: 2vh 3vw;
            gap: 3vh;
            margin-top: 1vh;
            overflow-y: auto;
            height: 100vh;
        }
        
        /* Header section */
        .header-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            margin-bottom: 1vh;
        }
        
        .company-logo {
            width: 25vw;
            max-width: 250px;
            min-width: 150px;
            background: #fff;
            border-radius: 20px;
            padding: 8px;
            margin-bottom: 2vh;
            box-shadow: 0 6px 30px rgba(0,0,0,0.4);
        }
        
        /* Time section - larger and centered */
        .time-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 4vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            width: 90%;
            max-width: 900px;
            margin-bottom: 1vh;
            backdrop-filter: blur(10px);
        }
        
        .public-clock {
            font-size: 15vw;
            color: #fff;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-shadow: 0 4px 20px rgba(0,0,0,0.7);
            font-family: 'Courier New', monospace;
            line-height: 1;
            margin: 1vh 0;
        }
        
        .clock-colon {
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .public-date {
            font-size: 4vw;
            color: #b0b7c3;
            font-weight: 500;
            text-align: center;
            margin-top: 1vh;
            letter-spacing: 0.05em;
        }
        
        /* Info panels - side by side on portrait */
        .info-panels {
            display: flex;
            flex-direction: row;
            justify-content: space-between;
            width: 100%;
            max-width: 950px;
            gap: 2vw;
            margin: 1vh 0;
        }
        
        .panel {
            flex: 1;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 2.5vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
            min-height: 200px;
            display: flex;
            flex-direction: column;
        }
        
        .panel-title {
            font-size: 3.5vw;
            color: #2ecc40;
            font-weight: 700;
            margin-bottom: 1.5vh;
            text-align: center;
            border-bottom: 2px solid #2ecc40;
            padding-bottom: 0.5vh;
        }
        
        /* Weather panel */
        .weather-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            flex-grow: 1;
        }
        
        .weather-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 3vw;
            margin-bottom: 1vh;
        }
        
        .weather-icon {
            width: 15vw;
            max-width: 120px;
            min-width: 80px;
        }
        
        .weather-temp {
            font-size: 10vw;
            color: #2ecc40;
            font-weight: 800;
            text-shadow: 0 2px 10px rgba(46, 204, 64, 0.3);
        }
        
        .weather-desc {
            font-size: 3vw;
            color: #b0b7c3;
            text-align: center;
            margin-top: 0.5vh;
        }
        
        /* Calendar panel */
        .calendar-content {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }
        
        .calendar-events-list {
            list-style: none;
            padding: 0;
            margin: 0;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 30vh;
        }
        
        .calendar-events-list::-webkit-scrollbar {
            width: 6px;
        }
        
        .calendar-events-list::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }
        
        .calendar-events-list::-webkit-scrollbar-thumb {
            background: #2ecc40;
            border-radius: 3px;
        }
        
        .calendar-events-list li {
            padding: 1.5vh 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .event-date {
            color: #2ecc40;
            font-weight: 700;
            font-size: 2.5vw;
            display: block;
            margin-bottom: 0.3vh;
        }
        
        .event-summary {
            color: #fff;
            font-size: 2.8vw;
            display: block;
            margin-bottom: 0.3vh;
        }
        
        .event-location {
            color: #b0b7c3;
            font-size: 2.2vw;
            display: block;
            font-style: italic;
        }
        
        .no-events {
            color: #888;
            font-size: 3vw;
            text-align: center;
            padding: 3vh 0;
            font-style: italic;
        }
        
        /* Presence panel - moved to main flow */
        .presence-panel {
            width: 90%;
            max-width: 900px;
            background: rgba(24, 28, 32, 0.85);
            border-radius: 20px;
            padding: 2vh 3vw;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            margin: 1vh 0 3vh 0;
            backdrop-filter: blur(10px);
        }
        
        .presence-content {
            display: flex;
            flex-direction: row;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 2vw;
            margin-top: 1vh;
        }
        
        .presence-column {
            flex: 1;
            min-width: 200px;
        }
        
        .presence-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .presence-list li {
            padding: 0.8vh 0;
            font-size: 2.8vw;
            display: flex;
            align-items: center;
        }
        
        .present-badge {
            display: inline-block;
            width: 2.5vw;
            height: 2.5vw;
            min-width: 12px;
            min-height: 12px;
            background-color: #2ecc40;
            border-radius: 50%;
            margin-right: 1.5vw;
            box-shadow: 0 0 8px #2ecc40;
        }
        
        .absent-badge {
            display: inline-block;
            width: 2.5vw;
            height: 2.5vw;
            min-width: 12px;
            min-height: 12px;
            background-color: #666;
            border-radius: 50%;
            margin-right: 1.5vw;
        }
        
        /* System info bar - at bottom */
        .system-info-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: rgba(10, 14, 20, 0.95);
            padding: 1vh 3vw;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 2px solid #2ecc40;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }
        
        .system-stats {
            display: flex;
            gap: 4vw;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 1vw;
        }
        
        .stat-label {
            font-size: 2.5vw;
            color: #b0b7c3;
            font-weight: 600;
        }
        
        .stat-value {
            font-size: 3vw;
            color: #fff;
            font-weight: 700;
        }
        
        .cpu-value { color: #2ecc40; }
        .mem-value { color: #3498db; }
        .disk-value { color: #9b59b6; }
        
        .wifi-section {
            display: flex;
            align-items: center;
            gap: 2vw;
        }
        
        .wifi-info {
            text-align: right;
        }
        
        .wifi-ssid {
            font-size: 2.8vw;
            color: #fff;
            font-weight: 600;
            margin-bottom: 0.3vh;
        }
        
        .wifi-instruction {
            font-size: 2.2vw;
            color: #b0b7c3;
        }
        
        .wifi-qr-small {
            width: 10vw;
            min-width: 70px;
            max-width: 100px;
            background: #fff;
            border-radius: 10px;
            padding: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        /* Responsive adjustments */
        @media (max-width: 800px) {
            .info-panels {
                flex-direction: column;
                gap: 2vh;
            }
            
            .panel {
                width: 100%;
            }
            
            .presence-content {
                flex-direction: column;
                gap: 1vh;
            }
            
            .public-clock {
                font-size: 18vw;
            }
            
            .public-date {
                font-size: 5vw;
            }
            
            .panel-title {
                font-size: 4.5vw;
            }
            
            .weather-temp {
                font-size: 12vw;
            }
            
            .weather-desc {
                font-size: 4vw;
            }
            
            .event-date, .event-summary {
                font-size: 3.8vw;
            }
            
            .presence-list li {
                font-size: 3.8vw;
            }
        }
        
        /* For very tall screens */
        @media (min-height: 1800px) {
            .main-container {
                padding-top: 5vh;
            }
            
            .time-section {
                padding: 3vh 4vw;
            }
            
            .panel {
                min-height: 250px;
            }
        }
        
        /* Animation for presence badges */
        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
        
        .present-badge {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
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
        
        <!-- Info panels (Weather & Calendar side by side) -->
        <div class="info-panels">
            <!-- Weather panel -->
            <div class="panel">
                <div class="panel-title">Weather</div>
                <div class="weather-content">
                    {% if weather and weather.temp is defined %}
                    <div class="weather-row">
                        <img class="weather-icon" src="{{ weather.icon_url }}" alt="{{ weather.desc }}" onerror="this.style.display='none'">
                        <span class="weather-temp">{{ weather.temp }}°C</span>
                    </div>
                    <div class="weather-desc">{{ weather.desc }}</div>
                    {% else %}
                    <div class="weather-desc" style="font-size: 4vw; padding: 3vh 0;">Weather data unavailable</div>
                    {% endif %}
                </div>
            </div>
            
            <!-- Calendar panel -->
            <div class="panel">
                <div class="panel-title">Upcoming Events</div>
                <div class="calendar-content">
                    {% if calendar_events and calendar_events|length > 0 %}
                    <ul class="calendar-events-list">
                        {% for event in calendar_events %}
                        <li>
                            <span class="event-date">{{ event.start[5:16] if event.start|length > 16 else event.start }}</span>
                            <span class="event-summary">{{ event.summary }}</span>
                            {% if event.location and event.location|length > 0 %}
                            <span class="event-location">{{ event.location }}</span>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                    {% else %}
                    <div class="no-events">No upcoming events</div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Presence panel -->
        <div class="presence-panel">
            <div class="panel-title">Lab Presence</div>
            <div class="presence-content">
                <div class="presence-column">
                    <div style="color: #2ecc40; font-size: 3vw; margin-bottom: 1vh; font-weight: 600;">Present ({{ present_colleagues|length }})</div>
                    <ul class="presence-list">
                        {% if present_colleagues and present_colleagues|length > 0 %}
                            {% for person in present_colleagues %}
                            <li><span class="present-badge"></span>{{ person }}</li>
                            {% endfor %}
                        {% else %}
                            <li style="color: #888; font-style: italic;">No colleagues detected</li>
                        {% endif %}
                    </ul>
                </div>
                <div class="presence-column">
                    <div style="color: #b0b7c3; font-size: 3vw; margin-bottom: 1vh; font-weight: 600;">Absent ({{ absent_colleagues|length }})</div>
                    <ul class="presence-list">
                        {% if absent_colleagues and absent_colleagues|length > 0 %}
                            {% for person in absent_colleagues %}
                            <li><span class="absent-badge"></span>{{ person }}</li>
                            {% endfor %}
                        {% else %}
                            <li style="color: #888; font-style: italic;">All colleagues present</li>
                        {% endif %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    
    <!-- System info bar at bottom -->
    <div class="system-info-bar">
        <div class="system-stats">
            <div class="stat-item">
                <span class="stat-label">CPU:</span>
                <span class="stat-value cpu-value">{{ sys_status.cpu }}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">RAM:</span>
                <span class="stat-value mem-value">{{ sys_status.mem }}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Disk:</span>
                <span class="stat-value disk-value">{{ sys_status.disk }}%</span>
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
        
        // Initial update
        updateClock();
        
        // Update every second
        setInterval(updateClock, 1000);
        
        // Smooth scroll for calendar if needed
        document.addEventListener('DOMContentLoaded', function() {
            const calendarList = document.querySelector('.calendar-events-list');
            if (calendarList && calendarList.scrollHeight > calendarList.clientHeight) {
                // If content overflows, add slight auto-scroll
                let scrollPos = 0;
                const scrollInterval = setInterval(() => {
                    if (scrollPos >= calendarList.scrollHeight - calendarList.clientHeight) {
                        scrollPos = 0;
                    } else {
                        scrollPos += 1;
                    }
                    calendarList.scrollTop = scrollPos;
                }, 50);
            }
        });
    </script>
</body>
</html>"""