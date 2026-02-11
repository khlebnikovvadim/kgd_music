# KGD Music - Yandex Music Artist Statistics Tracker

Monthly parser for tracking Yandex Music artist listener statistics with proxy support.

## Features

- 📊 Playwright-based browser automation
- 🥷 Stealth mode to avoid detection
- 🌐 **Proxy support** for bypassing geo-blocking
- 💾 SQLite database for historical tracking
- 📅 Monthly listener counts
- 📈 CSV export for analysis

## Quick Start

### 1. Install Dependencies

```bash
cd ~/kgd_music
pip install -r requirements.txt
python3 -m playwright install chromium
```

### 2. Configure Proxy (Important!)

Yandex Music is geo-blocked outside Russia/CIS. You need a Russian proxy.

Edit `config.py`:

```python
# Set your Russian proxy
PROXY_SERVER = 'http://your-proxy-server:8080'

# Or with authentication:
PROXY_SERVER = 'http://username:password@proxy.example.com:8080'

# SOCKS5 proxy:
PROXY_SERVER = 'socks5://proxy.example.com:1080'
```

### 3. Add Artists

Edit `artists.txt`:

```
https://music.yandex.ru/artist/7927866
https://music.yandex.ru/artist/123456
```

### 4. Run Parser

```bash
python run_monthly.py
```

## Proxy Setup

### Option 1: Free Proxy Lists
- Find Russian proxies: https://www.proxy-list.download/RUSSIA
- Test them before using

### Option 2: Paid Proxy Services
- **Bright Data**: https://brightdata.com (residential IPs)
- **Smartproxy**: https://smartproxy.com
- **Proxy6**: https://proxy6.net (Russian provider)

### Option 3: VPN + Local Proxy
1. Connect to Russian VPN
2. Set `PROXY_SERVER = None` in config.py
3. Run parser (will use your VPN IP)

## Configuration (`config.py`)

```python
# Proxy settings (REQUIRED for non-Russian IPs)
PROXY_SERVER = 'http://proxy:8080'  # Set your proxy here

# Browser settings
HEADLESS = True  # False to see browser window

# Delays (seconds between requests)
DELAY_MIN = 5
DELAY_MAX = 10

# Paths
DB_PATH = 'data/artists.db'
CSV_PATH = 'data/artist_stats.csv'
```

## Output Example

```
============================================================
Starting monthly parser run: 2025-02-11 14:30:00
============================================================
🌐 Using proxy: http://proxy.example.com:8080
📋 Loaded 3 artist URLs from artists.txt
Starting to parse 3 artists...

[1/3] Processing: https://music.yandex.ru/artist/7927866
Loading page...
✓ Parsed: Печень (ID: 7927866) - 5,260 listeners
💾 Saved stats for Печень on 2025-02-11

============================================================
📊 SUMMARY - Parsed 3 artists
============================================================
Печень                         |        5,260 listeners
Another Artist                 |       15,420 listeners
Third Artist                   |      102,350 listeners
============================================================
```

## Database Structure

**Location:** `data/artists.db`

```sql
CREATE TABLE artist_stats (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    lastMonthListeners INTEGER,
    UNIQUE(date, artist_id)
);
```

## Python API

```python
from parser import YandexMusicParser

# With proxy
parser = YandexMusicParser(proxy='http://proxy:8080')

# Parse one artist
data = parser.parse_artist_page('https://music.yandex.ru/artist/7927866')

# Parse multiple
urls = ['https://music.yandex.ru/artist/7927866', ...]
parser.parse_artists(urls)

# Get latest stats
latest = parser.get_latest_stats()

# Get history
history = parser.get_artist_history('7927866')

# Calculate growth
growth = parser.get_growth_stats('7927866')
```

## Monthly Automation

### macOS/Linux (Cron)

```bash
crontab -e
```

Add:
```
# Run on 1st of every month at 9 AM
0 9 1 * * cd ~/kgd_music && /usr/bin/python3 run_monthly.py
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Monthly (1st day, 9:00 AM)
4. Action: Start Program
   - Program: `python`
   - Arguments: `run_monthly.py`
   - Start in: `C:\Users\YourName\kgd_music`

## Troubleshooting

### Issue: "Geo-blocking detected"
**Solution**: Configure a Russian proxy in `config.py`

### Issue: "CAPTCHA detected"
**Solution**:
- Increase delays (DELAY_MIN/MAX in config.py)
- Use residential proxy (not datacenter)
- Run less frequently

### Issue: Proxy not working
**Solution**:
- Test proxy: `curl --proxy http://proxy:8080 https://music.yandex.ru`
- Try different proxy
- Check proxy authentication

### Issue: Slow parsing
**Solution**: Normal - stealth mode adds delays to appear human

## How It Works

1. **Launches Chromium** with stealth settings
2. **Connects via proxy** (if configured)
3. **Navigates to artist page**
4. **Waits for JavaScript** to render content
5. **Simulates human behavior** (scrolling, delays)
6. **Extracts listener count** from text "X слушателей за месяц"
7. **Saves to database**

## Security Notes

- Never commit `config.py` with proxy credentials to git
- Use environment variables for sensitive data
- Rotate proxies if parsing many artists
- Respect Yandex's terms of service

## License

MIT
