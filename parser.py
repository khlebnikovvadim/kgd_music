#!/usr/bin/env python3
"""
Yandex Music Artist Statistics Parser
Uses Playwright with stealth mode and proxy support
"""

import pandas as pd
import sqlite3
from datetime import datetime
import time
import logging
import re
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YandexMusicParser:
    """Parser for Yandex Music artist statistics using Playwright with stealth"""

    def __init__(self, db_path='data/artists.db', headless=True, proxy=None):
        """
        Initialize parser

        Args:
            db_path: Path to SQLite database
            headless: Run browser in headless mode (default: True)
            proxy: Proxy server URL (e.g., 'http://proxy:8080' or 'socks5://proxy:1080')
        """
        self.db_path = db_path
        self.headless = headless
        self.proxy = proxy
        self._init_database()

        if self.proxy:
            logger.info(f"🌐 Using proxy: {self.proxy}")
        else:
            logger.warning("⚠️  No proxy configured - may encounter geo-blocking")

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

    def _random_viewport(self):
        """Generate random viewport size to appear more human"""
        widths = [1366, 1920, 1440, 1536, 1280]
        heights = [768, 1080, 900, 864, 720]
        return {
            'width': random.choice(widths),
            'height': random.choice(heights)
        }

    def _random_delay(self, min_sec=2, max_sec=5):
        """Random delay to appear more human"""
        delay = random.uniform(min_sec, max_sec)
        logger.debug(f"Waiting {delay:.1f} seconds...")
        time.sleep(delay)

    def parse_artist_page(self, artist_url):
        """
        Parse artist page using Playwright with stealth mode

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
                # Browser launch args
                launch_args = {
                    'headless': self.headless,
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                }

                # Add proxy if configured
                if self.proxy:
                    # Parse proxy URL to extract components
                    proxy_config = {'server': self.proxy}

                    # Check if proxy has username:password
                    if '@' in self.proxy:
                        # Extract username and password
                        try:
                            proto_and_creds = self.proxy.split('://')[1].split('@')[0]
                            if ':' in proto_and_creds:
                                username, password = proto_and_creds.split(':', 1)
                                proxy_config['username'] = username
                                proxy_config['password'] = password
                        except:
                            pass

                    launch_args['proxy'] = proxy_config

                # Launch browser
                browser = p.chromium.launch(**launch_args)

                # Create context with stealth settings
                viewport = self._random_viewport()
                context = browser.new_context(
                    viewport=viewport,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='ru-RU',
                    timezone_id='Europe/Moscow',
                    geolocation={'longitude': 37.6173, 'latitude': 55.7558},  # Moscow
                    permissions=['geolocation'],
                    color_scheme='light',
                    extra_http_headers={
                        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                )

                page = context.new_page()

                # Add stealth JavaScript to hide automation
                page.add_init_script("""
                    // Overwrite the `webdriver` property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false,
                    });

                    // Overwrite the `plugins` property
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });

                    // Overwrite the `languages` property
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    });

                    // Pass the Chrome Test
                    window.chrome = {
                        runtime: {},
                    };

                    // Pass the Permissions Test
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)

                # Navigate to page with random delay before
                self._random_delay(1, 3)

                try:
                    logger.info("Loading page...")
                    page.goto(artist_url, wait_until='domcontentloaded', timeout=30000)

                    # Wait for page to load with random delay
                    self._random_delay(3, 6)

                    # Simulate human scrolling
                    logger.debug("Simulating scroll...")
                    page.evaluate('window.scrollTo(0, 300)')
                    self._random_delay(0.5, 1.5)
                    page.evaluate('window.scrollTo(0, 0)')
                    self._random_delay(1, 2)

                except PlaywrightTimeout:
                    logger.warning("Page load timeout, continuing anyway...")

                # Wait for content
                page.wait_for_timeout(2000)

                # Extract artist name
                artist_name = None
                try:
                    # Try different selectors
                    name_selectors = [
                        'h1.page-artist__title',
                        'h1[class*="Title"]',
                        '[class*="ArtistTitle"]',
                        'h1',
                    ]
                    for selector in name_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                artist_name = element.inner_text().strip()
                                # Skip error messages
                                if artist_name and not any(x in artist_name.lower() for x in ['робот', 'region', 'недоступна']):
                                    break
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Could not extract artist name: {e}")

                # Extract listeners count
                listeners = None
                try:
                    # Get all visible text
                    visible_text = page.inner_text('body')

                    # Check for errors
                    if 'робот' in visible_text.lower() or 'captcha' in visible_text.lower():
                        logger.warning("⚠️  CAPTCHA detected on page")
                        browser.close()
                        return None

                    if 'недоступна в вашем регионе' in visible_text.lower() or 'not available in your region' in visible_text.lower():
                        logger.error("❌ Geo-blocking detected - check proxy configuration")
                        browser.close()
                        return None

                    # Pattern: "X слушателей за/в месяц" or "X тыс./млн слушателей"
                    patterns = [
                        r'([\d\s]+)\s*слушател[^\d]*(?:за|в)\s*месяц',  # "5 260 слушателей за/в месяц"
                        r'([\d,.]+)\s*(тыс|млн)\.?\s*слушател',  # "5.2 тыс слушателей"
                    ]

                    for pattern in patterns:
                        matches = re.finditer(pattern, visible_text, re.IGNORECASE)
                        for match in matches:
                            try:
                                # Remove all whitespace (including non-breaking spaces \xa0)
                                number_str = match.group(1).replace(' ', '').replace('\xa0', '').replace(',', '.')
                                number = float(number_str)

                                # Handle multipliers
                                if len(match.groups()) > 1 and match.group(2):
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

                    # Method 2: Try to find in page scripts
                    if not listeners:
                        scripts = page.query_selector_all('script')
                        for script in scripts[:30]:
                            try:
                                content = script.inner_text()
                                if 'lastMonthListeners' in content:
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

    def parse_artists(self, artist_urls, delay_min=5, delay_max=10):
        """
        Parse multiple artist URLs with random delays

        Args:
            artist_urls: list of artist URLs
            delay_min: minimum seconds between requests (default: 5)
            delay_max: maximum seconds between requests (default: 10)
        """
        parse_date = datetime.now().strftime('%Y-%m-%d')
        success_count = 0
        fail_count = 0

        logger.info(f"Starting to parse {len(artist_urls)} artists...")
        logger.info(f"Using random delays between {delay_min}-{delay_max} seconds")

        for i, url in enumerate(artist_urls, 1):
            logger.info(f"\n[{i}/{len(artist_urls)}] Processing: {url}")

            artist_data = self.parse_artist_page(url)
            if artist_data:
                self.save_stats(artist_data, parse_date)
                success_count += 1
            else:
                fail_count += 1

            # Random delay between requests
            if i < len(artist_urls):
                delay = random.uniform(delay_min, delay_max)
                logger.info(f"⏱️  Waiting {delay:.1f} seconds before next request...")
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
    # Try to load config
    try:
        from config import PROXY_SERVER, HEADLESS, DELAY_MIN, DELAY_MAX
        parser = YandexMusicParser(proxy=PROXY_SERVER, headless=HEADLESS)
    except ImportError:
        logger.warning("config.py not found, using defaults")
        parser = YandexMusicParser()
        DELAY_MIN, DELAY_MAX = 5, 10

    # Example artists
    artist_urls = [
        'https://music.yandex.ru/artist/7927866',  # Печень
    ]

    # Parse all artists
    parser.parse_artists(artist_urls, delay_min=DELAY_MIN, delay_max=DELAY_MAX)

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
