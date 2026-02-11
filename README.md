# KGD Music - Yandex Music Artist Statistics Tracker

Monthly parser for tracking Yandex Music artist listener statistics.

## Features

- 📊 Extracts data from Yandex Music JSON (not HTML scraping)
- 💾 SQLite database for historical tracking
- 📅 Monthly listener counts
- 📈 CSV export for analysis
- 🚀 Reliable JSON-based parsing

## Quick Start

### 1. Install Dependencies

```bash
cd ~/kgd_music
pip install -r requirements.txt
```

### 2. Add Artists

Edit `artists.txt`:

```
https://music.yandex.ru/artist/7927866
https://music.yandex.ru/artist/123456
https://music.yandex.ru/artist/789012
```

### 3. Run Parser

```bash
python run_monthly.py
```

## Output Example

```
============================================================
Starting monthly parser run: 2025-02-11 14:30:00
============================================================
📋 Loaded 3 artist URLs from artists.txt

[1/3] Processing: https://music.yandex.ru/artist/7927866
Fetching https://music.yandex.ru/artist/7927866
✓ Parsed: Печень (ID: 7927866) - 5,260 listeners
💾 Saved stats for Печень on 2025-02-11

...

============================================================
✓ Successfully parsed: 3
✗ Failed: 0
============================================================
📄 Exported 3 records to data/artist_stats.csv

============================================================
📊 SUMMARY - Parsed 3 artists
============================================================
Печень                         |        5,260 listeners
Another Artist                 |       15,420 listeners
Third Artist                   |      102,350 listeners

============================================================
✓ Completed in 8.3 seconds
============================================================
```

## Database Structure

**Location:** `data/artists.db`

**Schema:**
```sql
CREATE TABLE artist_stats (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,           -- YYYY-MM-DD
    artist_id TEXT NOT NULL,      -- Yandex artist ID
    artist_name TEXT NOT NULL,    -- Artist name
    lastMonthListeners INTEGER,   -- Monthly listeners
    UNIQUE(date, artist_id)
);
```

## Python API

```python
from parser import YandexMusicParser

parser = YandexMusicParser()

# Parse one artist
data = parser.parse_artist_page('https://music.yandex.ru/artist/7927866')
# Returns: {'artist_id': '7927866', 'artist_name': 'Печень', 'lastMonthListeners': 5260}

# Parse multiple
urls = ['https://music.yandex.ru/artist/7927866', ...]
parser.parse_artists(urls)

# Get latest stats
latest = parser.get_latest_stats()
print(latest)

# Get artist history
history = parser.get_artist_history('7927866')

# Calculate growth
growth = parser.get_growth_stats('7927866')
print(f"Growth: {growth['growth_percent']:.1f}%")
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

## Files

```
kgd_music/
├── parser.py           # Main parser class
├── run_monthly.py      # Monthly execution script
├── artists.txt         # Artist URLs to track
├── requirements.txt    # Dependencies
├── data/
│   ├── artists.db      # SQLite database
│   ├── artist_stats.csv# CSV export
│   └── parser.log      # Execution logs
└── README.md
```

## How It Works

1. **Fetches page**: Gets artist page HTML
2. **Extracts JSON**: Finds embedded JSON data (`Mu.pages.artist = {...}`)
3. **Parses structure**:
   ```json
   {
     "artist": {
       "meta": {
         "artist": {"id": "7927866", "name": "Печень"},
         "lastMonthListeners": 5260
       }
     }
   }
   ```
4. **Saves to DB**: Stores with date + artist info
5. **Exports CSV**: Creates CSV for easy analysis

## Troubleshooting

**No data extracted**
- Yandex may have changed their JSON structure
- Check `data/parser.log` for details
- Update regex patterns in `_extract_json_data()`

**Request errors**
- Check internet connection
- Yandex may be rate limiting - increase delay in `parse_artists()`

**Database locked**
- Close any programs accessing `data/artists.db`
- SQLite allows one writer at a time

## License

MIT
