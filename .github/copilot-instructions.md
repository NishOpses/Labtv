# Copilot Instructions for Labtv (Kiosk Dashboard)

## Project Overview
This codebase powers a public-facing kiosk dashboard for a lab environment. It displays real-time information including:
- Colleague presence (via MAC address detection)
- Weather (OpenWeatherMap API)
- Upcoming calendar events (Outlook ICS feed)
- System status (CPU, RAM, Disk)
- WiFi QR code for guest access

The main application is a Flask web server (`kiosk_dashboard.py`) with supporting modules and static assets.

## Key Components & Data Flows
- **Presence Detection**: Reads `colleagues.json` for MAC addresses, checks ARP table to determine who is present/absent.
- **Weather**: Uses OpenWeatherMap API (API key hardcoded) and caches results in `weather_cache.json`.
- **Calendar**: Fetches and parses Outlook ICS feed, caches events in `calendar_cache.json`.
- **System Status**: Uses `psutil` for CPU, RAM, Disk usage.
- **WiFi QR**: Generates QR code for guest WiFi using environment variables or defaults.
- **HTML/UI**: All rendering is via a large Jinja2 template string in `kiosk_dashboard.py`. Logo is in `static/Opses_Logo.jpg`.

## Developer Workflows
- **Run/Debug**: Start with `python kiosk_dashboard.py`. Flask runs on port 8081. Background thread auto-runs `git pull` hourly for updates.
- **Build**: Not required for Python code. For Windows-specific builds, use the provided `msbuild` task (see VS Code tasks).
- **Update Colleagues**: Edit `colleagues.json` to add/remove MAC addresses.
- **Change WiFi/Calendar/Weather**: Update environment variables or edit hardcoded values in `kiosk_dashboard.py`.

## Conventions & Patterns
- **Caching**: All external API calls (weather, calendar) are cached to JSON files for performance.
- **Debug Logging**: Debug output is printed to console for most errors and cache events.
- **No database**: All state is file-based (JSON).
- **Service Boundaries**: All logic is in `kiosk_dashboard.py` except for time info (`useful_info.py`).
- **No tests**: No test framework or test files present.

## Integration Points
- **OpenWeatherMap**: API key is `144536c74a836feb69c1cd449b8457b9` (can be rotated).
- **Outlook ICS**: URL is set via env var or hardcoded.
- **Flask**: Main app, all routes in one file.

## Examples
- To add a new colleague: Edit `colleagues.json` with their MAC address.
- To change the logo: Replace `static/Opses_Logo.jpg`.
- To debug calendar issues: Delete `calendar_cache.json` and check console output.

## Quick Reference
- Main app: `kiosk_dashboard.py`
- Supporting: `useful_info.py`, `colleagues.json`, `static/`
- Caches: `weather_cache.json`, `calendar_cache.json`
- Logo: `static/Opses_Logo.jpg`

---
For questions or unclear patterns, ask for clarification or check console debug output.
