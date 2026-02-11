# KGD Music - Yandex Music Artist Statistics Tracker

Monthly parser for tracking Yandex Music artist listener statistics.

## Features

- 📊 Playwright-based browser automation
- 🥷 Stealth mode to avoid detection
- 🌐 Proxy support (optional, only for non-Russian IPs)
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

### 2. Add Artists

Edit `artists.txt`:

```
https://music.yandex.ru/artist/7927866
https://music.yandex.ru/artist/123456
```

### 3. Run Parser

```bash
python3 run_monthly.py
```

**That's it!** If you're in Russia, no proxy configuration needed.

## Configuration

### Running from Russia 🇷🇺

No configuration needed! Just run:

```bash
python3 run_monthly.py
```

The default `config.py` has `PROXY_SERVER = None` which works perfectly in Russia.

### Running from Outside Russia 🌍

You need a Russian proxy. Edit `config.py`:

```python
# Set your Russian proxy
PROXY_SERVER = 'http://your-proxy-server:8080'
```

**Proxy options:**
- **Russian VPS** ($2-5/month) - Best option, no proxy needed
- **Paid proxy** ($1-5/month) - [Proxy6.net](https://proxy6.net), [Smartproxy](https://smartproxy.com)
- **VPN** - Connect to Russian server, keep `PROXY_SERVER = None`

## Output Example

```
============================================================
Starting monthly parser run: 2025-02-11 14:30:00
============================================================
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

# Default (no proxy)
parser = YandexMusicParser()

# With proxy (if needed)
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

### Linux/macOS (Cron)

```bash
crontab -e
```

Add:
```
# Run on 1st of every month at 9 AM Moscow time
0 9 1 * * cd ~/kgd_music && /usr/bin/python3 run_monthly.py
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Monthly (1st day, 9:00 AM)
4. Action: Start Program
   - Program: `python`
   - Arguments: `run_monthly.py`
   - Start in: `C:\path\to\kgd_music`

## Configuration Options (`config.py`)

```python
# Proxy (only if outside Russia)
PROXY_SERVER = None

# Browser settings
HEADLESS = True  # False to see browser window

# Delays (seconds between requests)
DELAY_MIN = 5
DELAY_MAX = 10

# Paths
DB_PATH = 'data/artists.db'
CSV_PATH = 'data/artist_stats.csv'
```

## Troubleshooting

### Issue: "Geo-blocking detected"
**Solution**: You're not in Russia. Either:
- Use Russian VPS ($2-5/month)
- Configure proxy in `config.py`
- Use VPN

### Issue: "CAPTCHA detected"
**Solution**:
- Increase delays (`DELAY_MIN`, `DELAY_MAX` in config.py)
- Run less frequently
- Use residential proxy (not datacenter)

### Issue: Proxy not working
**Solution**:
- Test proxy: `curl --proxy http://proxy:8080 https://music.yandex.ru`
- Try different proxy
- Or use Russian VPS (no proxy needed)

## Files Structure

```
kgd_music/
├── config.py          # Configuration (proxy, delays, etc.)
├── parser.py          # Main parser with stealth mode
├── run_monthly.py     # Monthly execution script
├── artists.txt        # List of artist URLs to track
├── test_proxy.py      # Test proxy connectivity
├── requirements.txt   # Python dependencies
├── README.md          # This file
└── data/
    ├── artists.db     # SQLite database
    ├── artist_stats.csv # CSV export
    └── parser.log     # Execution logs
```

## How It Works

1. **Launches Chromium** with stealth settings
2. **Connects via proxy** (if configured)
3. **Navigates to artist page**
4. **Waits for JavaScript** to render content
5. **Simulates human behavior** (scrolling, delays)
6. **Extracts listener count** from text "X слушателей за месяц"
7. **Saves to database**

## For Non-Russian Users

If you're outside Russia, you have 3 options:

**Option 1: Russian VPS** (Recommended - $2-5/month)
- [Timeweb](https://timeweb.com) - 200-500₽/month
- [Yandex Cloud](https://cloud.yandex.ru) - Yandex's own cloud
- [Selectel](https://selectel.ru) - Russian hosting
- No proxy needed, always works!

**Option 2: Paid Proxy** ($1-5/month)
- [Proxy6.net](https://proxy6.net) - Russian proxy provider
- Configure in `config.py`

**Option 3: VPN**
- Connect to Russian VPN server
- Keep `PROXY_SERVER = None`

## License

MIT

## Support

For issues or questions:
- Check logs in `data/parser.log`
- Run `python3 test_proxy.py` to test proxy
- See troubleshooting section above
