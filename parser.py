#!/usr/bin/env python3
"""
Yandex Music Artist Statistics Parser
Parses artist pages to track monthly listener counts
"""

import requests
import json
import re
import pandas as pd
import sqlite3
from datetime import datetime
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YandexMusicParser:
    """Parser for Yandex Music artist statistics"""

    def __init__(self, db_path='data/artists.db'):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with schema"""
        Path('data').mkdir(exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS artist_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    artist_id TEXT NOT NULL,
                    artist_name TEXT NOT NULL,
                    lastMonthListeners INTEGER,
                    UNIQUE(date, artist_id)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_artist_date
                ON artist_stats(artist_id, date)
            ''')
            conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def _extract_json_data(self, html_content):
        """
        Extract JSON data from Yandex Music page

        The page contains embedded JSON in format:
        Mu.pages.artist = {"artist": {...}, ...}
        """
        # Look for the artist data in the page
        patterns = [
            r'Mu\.pages\.artist\s*=\s*({.+?});',
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.__DATA__\s*=\s*({.+?});',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_content, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    return data
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON decode error with pattern {pattern}: {e}")
                    continue

        return None

    def parse_artist_page(self, artist_url):
        """
        Parse artist page and extract statistics

        Args:
            artist_url: URL like 'https://music.yandex.ru/artist/7927866'

        Returns:
            dict with artist_id, artist_name, lastMonthListeners
        """
        try:
            # Extract artist ID from URL
            artist_id_match = re.search(r'/artist/(\d+)', artist_url)
            if not artist_id_match:
                logger.error(f"Could not extract artist ID from {artist_url}")
                return None
            artist_id = artist_id_match.group(1)

            # Fetch page
            logger.info(f"Fetching {artist_url}")
            response = self.session.get(artist_url, timeout=15)
            response.raise_for_status()

            # Extract JSON data from page
            data = self._extract_json_data(response.text)

            if not data:
                logger.error(f"Could not find JSON data in page")
                return None

            # Navigate JSON structure
            # Expected structure: data["artist"]["meta"]
            artist_info = None
            artist_name = None
            listeners = None

            # Try different JSON paths
            if 'artist' in data:
                artist_section = data['artist']

                # Get artist ID and name
                if 'meta' in artist_section:
                    meta = artist_section['meta']

                    # Artist name
                    if 'artist' in meta and 'name' in meta['artist']:
                        artist_name = meta['artist']['name']

                    # Last month listeners
                    if 'lastMonthListeners' in meta:
                        listeners = meta['lastMonthListeners']

                # Alternative: artist info at top level
                if not artist_name and 'name' in artist_section:
                    artist_name = artist_section['name']

                if not listeners and 'lastMonthListeners' in artist_section:
                    listeners = artist_section['lastMonthListeners']

            if not artist_name:
                logger.warning(f"Could not extract artist name from JSON")
                artist_name = f"Artist_{artist_id}"

            if listeners is None:
                logger.warning(f"Could not extract listener count from JSON")

            result = {
                'artist_id': artist_id,
                'artist_name': artist_name,
                'lastMonthListeners': listeners
            }

            logger.info(f"✓ Parsed: {artist_name} (ID: {artist_id}) - {listeners:,} listeners" if listeners else f"✓ Parsed: {artist_name} (ID: {artist_id}) - No listener data")
            return result

        except requests.RequestException as e:
            logger.error(f"Request error for {artist_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {artist_url}: {e}", exc_info=True)
            return None

    def save_stats(self, artist_data, parse_date=None):
        """
        Save artist statistics to database

        Args:
            artist_data: dict with artist_id, artist_name, lastMonthListeners
            parse_date: date string (YYYY-MM-DD), defaults to today
        """
        if not artist_data:
            return

        if parse_date is None:
            parse_date = datetime.now().strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO artist_stats
                    (date, artist_id, artist_name, lastMonthListeners)
                    VALUES (?, ?, ?, ?)
                ''', (
                    parse_date,
                    artist_data['artist_id'],
                    artist_data['artist_name'],
                    artist_data['lastMonthListeners']
                ))
                conn.commit()
                logger.info(f"💾 Saved stats for {artist_data['artist_name']} on {parse_date}")
            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")

    def parse_artists(self, artist_urls, delay=2):
        """
        Parse multiple artist URLs

        Args:
            artist_urls: list of artist URLs
            delay: seconds to wait between requests (default: 2)
        """
        parse_date = datetime.now().strftime('%Y-%m-%d')
        success_count = 0
        fail_count = 0

        logger.info(f"Starting to parse {len(artist_urls)} artists...")

        for i, url in enumerate(artist_urls, 1):
            logger.info(f"\n[{i}/{len(artist_urls)}] Processing: {url}")

            artist_data = self.parse_artist_page(url)
            if artist_data:
                self.save_stats(artist_data, parse_date)
                success_count += 1
            else:
                fail_count += 1

            # Be polite - add delay between requests
            if i < len(artist_urls):
                time.sleep(delay)

        logger.info(f"\n{'='*50}")
        logger.info(f"✓ Successfully parsed: {success_count}")
        logger.info(f"✗ Failed: {fail_count}")
        logger.info(f"{'='*50}")

    def export_to_csv(self, output_path='data/artist_stats.csv'):
        """Export all data to CSV"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query('SELECT * FROM artist_stats ORDER BY date DESC, artist_name', conn)
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"📄 Exported {len(df)} records to {output_path}")
            return df

    def get_latest_stats(self):
        """Get the most recent statistics for all artists"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT date, artist_id, artist_name, lastMonthListeners
                FROM artist_stats
                WHERE date = (SELECT MAX(date) FROM artist_stats)
                ORDER BY lastMonthListeners DESC
            '''
            df = pd.read_sql_query(query, conn)
            return df

    def get_artist_history(self, artist_id):
        """Get historical data for a specific artist"""
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT date, artist_name, lastMonthListeners
                FROM artist_stats
                WHERE artist_id = ?
                ORDER BY date
            '''
            df = pd.read_sql_query(query, conn, params=(artist_id,))
            return df

    def get_growth_stats(self, artist_id):
        """Calculate growth statistics for an artist"""
        history = self.get_artist_history(artist_id)

        if len(history) < 2:
            return None

        history = history.sort_values('date')
        latest = history.iloc[-1]
        previous = history.iloc[-2]

        growth = latest['lastMonthListeners'] - previous['lastMonthListeners']
        growth_pct = (growth / previous['lastMonthListeners'] * 100) if previous['lastMonthListeners'] > 0 else 0

        return {
            'artist_name': latest['artist_name'],
            'current_listeners': latest['lastMonthListeners'],
            'previous_listeners': previous['lastMonthListeners'],
            'growth': growth,
            'growth_percent': growth_pct,
            'latest_date': latest['date'],
            'previous_date': previous['date']
        }


def main():
    """Main execution function"""
    # Example usage
    parser = YandexMusicParser()

    # List of artists to track
    artist_urls = [
        'https://music.yandex.ru/artist/7927866',  # Печень
        # Add more artist URLs here
    ]

    # Parse all artists
    parser.parse_artists(artist_urls)

    # Export to CSV
    parser.export_to_csv()

    # Show latest stats
    print("\n📊 Latest Statistics:")
    stats = parser.get_latest_stats()
    print(stats.to_string(index=False))


if __name__ == '__main__':
    main()
