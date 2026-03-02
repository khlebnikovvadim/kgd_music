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
import subprocess
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YandexMusicParser:
    """Parser for Yandex Music artist statistics using Playwright with stealth"""

    def __init__(self, db_path='data/artists.db', headless=True, proxy=None, cookie_file='data/yandex_cookies.json'):
        """
        Initialize parser

        Args:
            db_path: Path to SQLite database
            headless: Run browser in headless mode (default: True)
            proxy: Proxy server URL (e.g., 'http://proxy:8080' or 'socks5://proxy:1080')
            cookie_file: Path to save/load cookies for session persistence
        """
        self.db_path = db_path
        self.headless = headless
        self.proxy = proxy
        self.cookie_file = cookie_file
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
                    genre TEXT,
                    track1_name TEXT,
                    track1_year INTEGER,
                    track2_name TEXT,
                    track2_year INTEGER,
                    track3_name TEXT,
                    track3_year INTEGER,
                    total_album_likes INTEGER,
                    playlists_count INTEGER,
                    playlists_names TEXT,
                    playlists_total_likes INTEGER,
                    UNIQUE(date, artist_id)
                )
            ''')
            # Add new columns if they don't exist (for existing databases)
            for col, col_type in [('genre', 'TEXT'),
                                   ('track1_name', 'TEXT'), ('track1_year', 'INTEGER'),
                                   ('track2_name', 'TEXT'), ('track2_year', 'INTEGER'),
                                   ('track3_name', 'TEXT'), ('track3_year', 'INTEGER'),
                                   ('total_album_likes', 'INTEGER'),
                                   ('playlists_count', 'INTEGER'),
                                   ('playlists_names', 'TEXT'),
                                   ('playlists_total_likes', 'INTEGER')]:
                try:
                    conn.execute(f'ALTER TABLE artist_stats ADD COLUMN {col} {col_type}')
                except sqlite3.OperationalError:
                    pass  # Column already exists
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_artist_date
                ON artist_stats(artist_id, date)
            ''')
            conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def _load_cookies(self, context):
        """Load saved cookies from file"""
        if Path(self.cookie_file).exists():
            try:
                with open(self.cookie_file, 'r') as f:
                    cookies = json.load(f)
                context.add_cookies(cookies)
                logger.info(f"✓ Loaded {len(cookies)} cookies from {self.cookie_file}")
            except Exception as e:
                logger.warning(f"Could not load cookies: {e}")
        else:
            logger.info("No existing cookies found, starting fresh session")

    def _save_cookies(self, context):
        """Save cookies to file for next session"""
        try:
            cookies = context.cookies()
            Path(self.cookie_file).parent.mkdir(exist_ok=True)
            with open(self.cookie_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"✓ Saved {len(cookies)} cookies to {self.cookie_file}")
        except Exception as e:
            logger.warning(f"Could not save cookies: {e}")

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

    def _extract_popular_tracks(self, page, context):
        """
        Extract first 3 popular tracks with their release years and genre from first album

        Returns:
            tuple: (tracks list, genre string)
            tracks: [{'name': 'Track Name', 'year': 2022}, ...]
        """
        tracks = []
        genre = None
        try:
            # Find track links on artist page
            track_elements = page.query_selector_all('a[href*="/album/"][href*="/track/"]')
            logger.debug(f"Found {len(track_elements)} track links")

            for i, track_el in enumerate(track_elements[:3]):  # First 3 tracks
                try:
                    track_name = track_el.inner_text().strip()
                    href = track_el.get_attribute('href')

                    if not href or not track_name:
                        continue

                    # Extract album ID from href like /album/23249156/track/105006954
                    album_match = re.search(r'/album/(\d+)', href)
                    if not album_match:
                        tracks.append({'name': track_name, 'year': None})
                        continue

                    album_id = album_match.group(1)
                    album_url = f"https://music.yandex.ru/album/{album_id}"

                    # Open album page in new tab to get release year
                    album_page = context.new_page()
                    try:
                        album_page.goto(album_url, wait_until='domcontentloaded', timeout=15000)
                        self._random_delay(5, 8)

                        # Get album page text and HTML
                        album_text = album_page.inner_text('body')
                        album_html = album_page.content()

                        # Extract year: artist name followed by year like "Печень2022"
                        year = None
                        year_match = re.search(r'[а-яА-Яa-zA-Z](20[12]\d)\n', album_text[:400])
                        if year_match:
                            year = int(year_match.group(1))
                        else:
                            year_match = re.search(r'\b(20[12]\d)\b', album_text[:300])
                            if year_match:
                                year = int(year_match.group(1))

                        # Extract genre from first album only
                        if i == 0 and genre is None:
                            genre_match = re.search(r'"genre"\s*:\s*"([^"]+)"', album_html)
                            if genre_match:
                                genre = genre_match.group(1)
                                logger.debug(f"Found genre: {genre}")

                        tracks.append({'name': track_name, 'year': year})
                        logger.debug(f"Track: {track_name} -> Year: {year}")

                    except Exception as e:
                        logger.debug(f"Could not get album info for {track_name}: {e}")
                        tracks.append({'name': track_name, 'year': None})
                    finally:
                        album_page.close()

                except Exception as e:
                    logger.debug(f"Error extracting track: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting popular tracks: {e}")

        return tracks, genre

    def _get_total_album_likes(self, page, context):
        """
        Calculate total likes across all artist's albums

        Returns:
            int: Sum of likes from all albums
        """
        total_likes = 0
        try:
            # Get all unique album IDs from artist page
            album_links = page.query_selector_all('a[href*="/album/"]')
            album_ids = set()
            for link in album_links:
                href = link.get_attribute('href')
                match = re.search(r'/album/(\d+)(?:/|$)', href)
                if match:
                    album_ids.add(match.group(1))

            logger.debug(f"Found {len(album_ids)} unique albums")

            # Visit each album page to get likes
            for album_id in album_ids:
                album_url = f"https://music.yandex.ru/album/{album_id}"
                album_page = context.new_page()
                try:
                    album_page.goto(album_url, wait_until='domcontentloaded', timeout=10000)
                    self._random_delay(3, 5)
                    album_html = album_page.content()
                    likes_match = re.search(r'"likesCount"\s*:\s*(\d+)', album_html)
                    if likes_match:
                        likes = int(likes_match.group(1))
                        total_likes += likes
                        logger.debug(f"Album {album_id}: {likes} likes")
                except Exception as e:
                    logger.debug(f"Could not get likes for album {album_id}: {e}")
                finally:
                    album_page.close()

        except Exception as e:
            logger.warning(f"Error getting total album likes: {e}")

        return total_likes

    def _get_playlist_data(self, artist_id, artist_name, playwright_instance):
        """
        Get playlist data from band.link scanner (without proxy)

        Returns:
            dict: {'count': int, 'names': list, 'total_likes': int}
        """
        result = {'count': 0, 'names': [], 'total_likes': 0}
        try:
            url = f"https://band.link/scanner?search={artist_id}&type=artist_id&service=yandex_music"

            # Launch separate browser WITHOUT proxy for band.link
            browser = playwright_instance.chromium.launch(
                headless=self.headless,
                args=[
                    '--window-position=-2000,-2000',  # Move window off-screen
                    '--disable-popup-blocking',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                ]
            )
            page = browser.new_page()
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=20000)
                self._random_delay(5, 7)  # Wait for JS to load

                text = page.inner_text('body')
                logger.info(f"Band.link text length: {len(text)}, has stats: {'Статистика' in text}")

                # Find section after "Статистика слушателей и лайков"
                if 'Статистика слушателей и лайков' in text:
                    data_section = text.split('Статистика слушателей и лайков')[1]
                    lines = [l.strip() for l in data_section.split('\n') if l.strip()]

                    # Parse playlists: pattern repeats every 4 lines
                    # [0] Playlist name, [1] Track info, [2] Likes (28K), [3] "Яндекс Музыка"
                    i = 0
                    while i < len(lines) - 2:
                        playlist_name = lines[i]
                        # Skip if it looks like a service name or header
                        if playlist_name in ['Яндекс Музыка', 'КИОН Музыка', '', 'Смотреть все']:
                            i += 1
                            continue

                        # Look for likes count (format: 28K, 11K, 1.5M, etc.)
                        likes_line = lines[i + 2] if i + 2 < len(lines) else ''
                        match = re.match(r'^(\d+(?:[.,]\d+)?)\s*([KkКк])?$', likes_line)
                        if match:
                            num = float(match.group(1).replace(',', '.'))
                            suffix = match.group(2)
                            if suffix and suffix.upper() in ['K', 'К']:
                                num *= 1000
                            likes = int(num)

                            result['names'].append(playlist_name)
                            result['total_likes'] += likes
                            i += 4  # Move to next playlist block
                        else:
                            i += 1

                    result['count'] = len(result['names'])
                    logger.debug(f"Found {result['count']} playlists: {result['names']}")

            except Exception as e:
                logger.debug(f"Could not get playlist data: {e}")
            finally:
                page.close()
                browser.close()

        except Exception as e:
            logger.warning(f"Error getting playlist data: {e}")

        return result

    def parse_artist_page(self, artist_url, page, context, playwright_instance):
        """
        Parse artist page using existing browser session

        Args:
            artist_url: URL like 'https://music.yandex.ru/artist/7927866'
            page: Playwright page object (reused across requests)
            context: Browser context (for album likes parsing)
            playwright_instance: Playwright instance for band.link parser

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

            # Navigate to page with random delay before
            self._random_delay(5, 8)

            try:
                logger.info("Loading page...")
                page.goto(artist_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for page to load with random delay
                self._random_delay(8, 12)

                # Simulate human scrolling
                logger.debug("Simulating scroll...")
                page.evaluate('window.scrollTo(0, 300)')
                self._random_delay(3, 5)
                page.evaluate('window.scrollTo(0, 0)')
                self._random_delay(5, 8)

            except PlaywrightTimeout:
                logger.warning("Page load timeout, continuing anyway...")

            # Wait for content
            page.wait_for_timeout(5000)

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
                    return None

                if 'недоступна в вашем регионе' in visible_text.lower() or 'not available in your region' in visible_text.lower():
                    logger.error("❌ Geo-blocking detected - check proxy configuration")
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

            # Extract popular tracks with release years and genre
            popular_tracks, genre = self._extract_popular_tracks(page, context)
            logger.info(f"Extracted {len(popular_tracks)} popular tracks, genre: {genre}")

            # Get total album likes
            total_album_likes = self._get_total_album_likes(page, context)
            logger.info(f"Total album likes: {total_album_likes}")

            # Get playlist data from band.link (without proxy)
            playlist_data = self._get_playlist_data(artist_id, artist_name, playwright_instance)
            logger.info(f"Playlists: {playlist_data['count']} ({playlist_data['total_likes']} likes)")

            if not artist_name:
                logger.warning(f"Could not extract artist name, using ID")
                artist_name = f"Artist_{artist_id}"

            if listeners is None:
                logger.warning(f"Could not extract listener count")

            result = {
                'artist_id': artist_id,
                'artist_name': artist_name,
                'lastMonthListeners': listeners,
                'genre': genre,
                'popular_tracks': popular_tracks,
                'total_album_likes': total_album_likes,
                'playlists_count': playlist_data['count'],
                'playlists_names': playlist_data['names'],
                'playlists_total_likes': playlist_data['total_likes']
            }

            # Log result
            tracks_info = ", ".join([f"{t['name']} ({t['year']})" for t in popular_tracks]) if popular_tracks else "none"
            logger.info(
                f"✓ Parsed: {artist_name} (ID: {artist_id}) - "
                f"{listeners:,} listeners - {genre or 'unknown'} - {total_album_likes} album likes - "
                f"{playlist_data['count']} playlists ({playlist_data['total_likes']} likes)" if listeners else
                f"✓ Parsed: {artist_name} (ID: {artist_id}) - No listener data - {genre or 'unknown'} - "
                f"{total_album_likes} album likes - {playlist_data['count']} playlists"
            )
            return result

        except Exception as e:
            logger.error(f"Error parsing {artist_url}: {e}", exc_info=True)
            return None

    def save_stats(self, artist_data, parse_date=None):
        """
        Save artist statistics to database

        Args:
            artist_data: dict with artist_id, artist_name, lastMonthListeners, popular_tracks
            parse_date: date string (YYYY-MM-DD), defaults to today
        """
        if not artist_data:
            return

        if parse_date is None:
            parse_date = datetime.now().strftime('%Y-%m-%d')

        # Extract track data
        tracks = artist_data.get('popular_tracks', [])
        track1_name = tracks[0]['name'] if len(tracks) > 0 else None
        track1_year = tracks[0]['year'] if len(tracks) > 0 else None
        track2_name = tracks[1]['name'] if len(tracks) > 1 else None
        track2_year = tracks[1]['year'] if len(tracks) > 1 else None
        track3_name = tracks[2]['name'] if len(tracks) > 2 else None
        track3_year = tracks[2]['year'] if len(tracks) > 2 else None
        genre = artist_data.get('genre')
        total_album_likes = artist_data.get('total_album_likes', 0)

        # Extract playlist data
        playlists_count = artist_data.get('playlists_count', 0)
        playlists_names = ', '.join(artist_data.get('playlists_names', []))
        playlists_total_likes = artist_data.get('playlists_total_likes', 0)

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO artist_stats
                    (date, artist_id, artist_name, lastMonthListeners, genre,
                     track1_name, track1_year, track2_name, track2_year,
                     track3_name, track3_year, total_album_likes,
                     playlists_count, playlists_names, playlists_total_likes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    parse_date,
                    artist_data['artist_id'],
                    artist_data['artist_name'],
                    artist_data['lastMonthListeners'],
                    genre,
                    track1_name, track1_year,
                    track2_name, track2_year,
                    track3_name, track3_year,
                    total_album_likes,
                    playlists_count, playlists_names, playlists_total_likes
                ))
                conn.commit()
                logger.info(f"💾 Saved stats for {artist_data['artist_name']} on {parse_date}")
            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")

    def parse_artists(self, artist_urls, delay_min=5, delay_max=10):
        """
        Parse multiple artist URLs with random delays using persistent browser session

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

        # Create persistent browser session for all artists
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
                    '--window-position=-2000,-2000',  # Move window off-screen
                    '--disable-popup-blocking',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                ]
            }

            # Add proxy if configured
            if self.proxy:
                proxy_config = {'server': self.proxy}
                # Parse username:password from proxy URL
                if '@' in self.proxy:
                    try:
                        proto_and_creds = self.proxy.split('://')[1].split('@')[0]
                        if ':' in proto_and_creds:
                            username, password = proto_and_creds.split(':')
                            proxy_config['username'] = username
                            proxy_config['password'] = password
                    except:
                        pass

                launch_args['proxy'] = proxy_config

            # Launch browser ONCE
            browser = p.chromium.launch(**launch_args)

            # Move browser window to Desktop 2 if headful (no distraction)
            if not self.headless:
                time.sleep(2)  # Wait for window to appear
                try:
                    # Move browser to Desktop 2 and immediately switch back to Desktop 1
                    subprocess.run([
                        'osascript', '-e',
                        '''tell application "System Events"
                            tell (first application process whose name contains "Chromium")
                                set frontmost to true
                            end tell
                            delay 0.3
                            -- Move to Desktop 2
                            key code 124 using {control down}
                            delay 0.3
                            -- Switch back to Desktop 1
                            key code 123 using {control down}
                        end tell'''
                    ], capture_output=True, timeout=15)
                    logger.info("✓ Browser on Desktop 2, you stay on Desktop 1")
                except Exception as e:
                    logger.warning(f"Could not move window to Desktop 2: {e}")

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

            # Load saved cookies for session persistence
            self._load_cookies(context)

            # Create page ONCE
            page = context.new_page()

            # Apply playwright-stealth (comprehensive anti-detection)
            stealth_config = Stealth()
            stealth_config.apply_stealth_sync(page)

            logger.info("✓ Persistent browser session created - will parse all artists in one window")

            # Parse all artists using the same browser/page
            for i, url in enumerate(artist_urls, 1):
                logger.info(f"\n[{i}/{len(artist_urls)}] Processing: {url}")

                artist_data = self.parse_artist_page(url, page, context, p)
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

            # Save cookies for next session
            self._save_cookies(context)

            # Close browser
            browser.close()

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


def load_artists_from_file(filepath='artists.txt'):
    """Load artist URLs from file"""
    artist_urls = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    artist_urls.append(line)
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
    return artist_urls


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

    # Load artists from file
    artist_urls = load_artists_from_file('artists.txt')
    if not artist_urls:
        logger.error("No artists found in artists.txt")
        return

    logger.info(f"Loaded {len(artist_urls)} artists from artists.txt")

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
