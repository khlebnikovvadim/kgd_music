#!/usr/bin/env python3
"""
Yandex Music Artist Statistics Parser
Uses Playwright for JavaScript rendering
"""

import pandas as pd
import sqlite3
from datetime import datetime
import time
import logging
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YandexMusicParser:
    """Parser for Yandex Music artist statistics using Playwright"""

    def __init__(self, db_path='data/artists.db', headless=True):
        self.db_path = db_path
        self.headless = headless
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

    def parse_artist_page(self, artist_url):
        """
        Parse artist page using Playwright (with JavaScript rendering)

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

            logger.info(f"Fetching {artist_url}")

            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    locale='ru-RU'
                )
                page = context.new_page()

                # Navigate to page
                try:
                    page.goto(artist_url, wait_until='networkidle', timeout=30000)
                except PlaywrightTimeout:
                    logger.warning("Page load timeout, continuing anyway...")

                # Wait a bit for JavaScript to execute
                page.wait_for_timeout(3000)

                # Extract artist name
                artist_name = None
                try:
                    # Try different selectors for artist name
                    name_selectors = [
                        'h1.page-artist__title',
                        '[class*="ArtistTitle"]',
                        'h1',
                    ]
                    for selector in name_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                artist_name = element.inner_text().strip()
                                if artist_name:
                                    break
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Could not extract artist name: {e}")

                # Extract listeners count
                listeners = None
                try:
                    # Look for text like "5 260 слушателей за месяц" or "5.2 тыс слушателей"
                    page_text = page.content()

                    # Method 1: Search in visible text
                    visible_text = page.inner_text('body')

                    # Pattern: "X слушателей за месяц" or "X тыс./млн слушателей"
                    patterns = [
                        r'([\d\s]+)\s*слушател',  # "5 260 слушателей"
                        r'([\d,.]+)\s*(тыс|млн)\.?\s*слушател',  # "5.2 тыс слушателей"
                    ]

                    for pattern in patterns:
                        matches = re.finditer(pattern, visible_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                number_str = match.group(1).replace(' ', '').replace(',', '.')
                                number = float(number_str)

                                # Handle multipliers
                                if len(match.groups()) > 1:
                                    multiplier = match.group(2)
                                    if multiplier == 'тыс':
                                        number *= 1000
                                    elif multiplier == 'млн':
                                        number *= 1_000_000

                                listeners = int(number)
                                logger.debug(f"Found listeners: {listeners} from text: {match.group(0)}")
                                break
                            except (ValueError, AttributeError) as e:
                                logger.debug(f"Could not parse number: {e}")

                        if listeners:
                            break

                    # Method 2: Try to find in page state/scripts
                    if not listeners:
                        # Search for lastMonthListeners in scripts
                        scripts = page.query_selector_all('script')
                        for script in scripts[:20]:  # Check first 20 scripts
                            try:
                                content = script.inner_text()
                                match = re.search(r'"lastMonthListeners"\s*:\s*(\d+)', content)
                                if match:
                                    listeners = int(match.group(1))
                                    logger.debug(f"Found in script: {listeners}")
                                    break
                            except:
                                pass

                except Exception as e:
                    logger.warning(f"Error extracting listeners: {e}")

                browser.close()

            if not artist_name:
                logger.warning(f"Could not extract artist name, using ID")
                artist_name = f"Artist_{artist_id}"

            if listeners is None:
                logger.warning(f"Could not extract listener count")

            result = {
                'artist_id': artist_id,
                'artist_name': artist_name,
                'lastMonthListeners': listeners
            }

            logger.info(
                f"✓ Parsed: {artist_name} (ID: {artist_id}) - "
                f"{listeners:,} listeners" if listeners else
                f"✓ Parsed: {artist_name} (ID: {artist_id}) - No listener data"
            )
            return result

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

    def parse_artists(self, artist_urls, delay=3):
        """
        Parse multiple artist URLs

        Args:
            artist_urls: list of artist URLs
            delay: seconds to wait between requests (default: 3)
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

            # Delay between requests
            if i < len(artist_urls):
                logger.info(f"Waiting {delay} seconds...")
                time.sleep(delay)

        logger.info(f"\n{'='*50}")
        logger.info(f"✓ Successfully parsed: {success_count}")
        logger.info(f"✗ Failed: {fail_count}")
        logger.info(f"{'='*50}")

    def export_to_csv(self, output_path='data/artist_stats.csv'):
        """Export all data to CSV"""
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                'SELECT * FROM artist_stats ORDER BY date DESC, artist_name',
                conn
            )
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

        if previous['lastMonthListeners'] and latest['lastMonthListeners']:
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
        return None


def main():
    """Main execution function"""
    parser = YandexMusicParser()

    # Example artists
    artist_urls = [
        'https://music.yandex.ru/artist/7927866',  # Печень
    ]

    # Parse all artists
    parser.parse_artists(artist_urls)

    # Export to CSV
    parser.export_to_csv()

    # Show latest stats
    print("\n📊 Latest Statistics:")
    stats = parser.get_latest_stats()
    if len(stats) > 0:
        print(stats.to_string(index=False))
    else:
        print("No data collected yet")


if __name__ == '__main__':
    main()
