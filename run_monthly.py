#!/usr/bin/env python3
"""
Monthly parser runner
Reads artist URLs from artists.txt and parses them
"""

from parser import YandexMusicParser
import logging
from datetime import datetime

# Try to load config
try:
    from config import PROXY_SERVER, HEADLESS, DELAY_MIN, DELAY_MAX, DB_PATH, CSV_PATH
except ImportError:
    PROXY_SERVER = None
    HEADLESS = True
    DELAY_MIN, DELAY_MAX = 5, 10
    DB_PATH = 'data/artists.db'
    CSV_PATH = 'data/artist_stats.csv'

# Setup logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def load_artist_urls(filename='artists.txt'):
    """Load artist URLs from file"""
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
    except FileNotFoundError:
        logging.error(f"File {filename} not found")
        return []
    return urls

def main():
    start_time = datetime.now()
    logging.info(f"{'='*60}")
    logging.info(f"Starting monthly parser run: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"{'='*60}")

    # Initialize parser with proxy
    parser = YandexMusicParser(db_path=DB_PATH, headless=HEADLESS, proxy=PROXY_SERVER)

    # Load artist URLs
    artist_urls = load_artist_urls()

    if not artist_urls:
        logging.warning("⚠️  No artist URLs to process. Add URLs to artists.txt")
        return

    logging.info(f"📋 Loaded {len(artist_urls)} artist URLs from artists.txt")

    # Parse all artists
    parser.parse_artists(artist_urls, delay_min=DELAY_MIN, delay_max=DELAY_MAX)

    # Export to CSV
    df = parser.export_to_csv(CSV_PATH)

    # Show summary
    stats = parser.get_latest_stats()

    print(f"\n{'='*60}")
    print(f"📊 SUMMARY - Parsed {len(stats)} artists")
    print(f"{'='*60}")

    if len(stats) > 0:
        # Display with formatting
        import pandas as pd
        for idx, row in stats.iterrows():
            listeners = f"{row['lastMonthListeners']:,}" if pd.notna(row['lastMonthListeners']) else "N/A"
            print(f"{row['artist_name']:30} | {listeners:>12} listeners")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"✓ Completed in {duration:.1f} seconds")
    print(f"{'='*60}")

if __name__ == '__main__':
    import pandas as pd
    main()
