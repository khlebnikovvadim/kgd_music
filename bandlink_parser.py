#!/usr/bin/env python3
"""
Separate Band.link parser for playlist data
Can run independently from Yandex Music parser
Uses persistent browser session (same as Yandex Music parser)
"""

import sqlite3
import re
import logging
import subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright
import time
import random
import json
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BandLinkParser:
    def __init__(self, db_path='data/artists.db', headless=True, cookie_file='data/bandlink_cookies.json'):
        self.db_path = db_path
        self.headless = headless
        self.cookie_file = cookie_file
        self._init_db()

        # Browser session (initialized in parse_all)
        self.browser = None
        self.context = None
        self.page = None

    def _init_db(self):
        """Initialize database connection"""
        self.conn = sqlite3.connect(self.db_path)
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

    def _random_delay(self, min_sec, max_sec):
        """Random delay to avoid rate limiting"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _get_playlist_data(self, artist_id, artist_name, page):
        """
        Get playlist data from band.link scanner using existing page

        Returns:
            dict: {'count': int, 'names': list, 'total_likes': int}
        """
        result = {'count': 0, 'names': [], 'total_likes': 0}

        try:
            url = f"https://band.link/scanner?search={artist_id}&type=artist_id&service=yandex_music"

            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            self._random_delay(5, 7)  # Wait for JS to load

            text = page.inner_text('body')
            logger.info(f"Band.link text length: {len(text)}, has stats: {'Статистика' in text}")

            # Check for captcha
            if 'captcha' in text.lower() or 'робот' in text.lower():
                logger.warning("⚠️  CAPTCHA detected on Band.link!")
                return result

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
                        result['count'] += 1

                        i += 4  # Move to next playlist
                    else:
                        i += 1

        except Exception as e:
            logger.error(f"Error fetching band.link for {artist_name}: {e}")

        return result

    def get_artists_to_parse(self):
        """Get list of artists from database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT artist_id, artist_name
            FROM artist_stats
            WHERE artist_id IS NOT NULL
            ORDER BY artist_id
        """)
        return cursor.fetchall()

    def update_playlist_data(self, artist_id, date, playlist_count, playlist_names, playlist_likes):
        """Update playlist data in database"""
        cursor = self.conn.cursor()

        # Convert playlist names list to string
        names_str = '|'.join(playlist_names) if playlist_names else ''

        cursor.execute("""
            UPDATE artist_stats
            SET playlists_count = ?,
                playlists_names = ?,
                playlists_total_likes = ?
            WHERE artist_id = ? AND date = ?
        """, (playlist_count, names_str, playlist_likes, artist_id, date))

        self.conn.commit()

    def parse_all(self, delay_min=3, delay_max=7):
        """Parse band.link data for all artists using persistent browser session"""
        artists = self.get_artists_to_parse()

        logger.info(f"Found {len(artists)} artists to parse")
        logger.info(f"Using delays between {delay_min}-{delay_max} seconds")
        logger.info("")

        success_count = 0
        failed_count = 0
        today = datetime.now().strftime('%Y-%m-%d')

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
                    '--window-position=-2000,-2000',  # Move window off-screen
                    '--no-first-run',
                    '--no-default-browser-check',
                ]
            }

            # Launch browser ONCE
            browser = p.chromium.launch(**launch_args)

            # Move browser window to Desktop 2 if headful
            if not self.headless:
                time.sleep(2)
                try:
                    subprocess.run([
                        'osascript', '-e',
                        '''tell application "System Events"
                            tell (first application process whose name contains "Chromium")
                                set frontmost to true
                            end tell
                            delay 0.3
                            key code 124 using {control down}
                            delay 0.3
                            key code 123 using {control down}
                        end tell'''
                    ], capture_output=True, timeout=15)
                    logger.info("✓ Browser on Desktop 2, you stay on Desktop 1")
                except Exception as e:
                    logger.warning(f"Could not move window to Desktop 2: {e}")

            # Create context with settings
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ru-RU',
            )

            # Load saved cookies
            self._load_cookies(context)

            # Create page ONCE
            page = context.new_page()

            logger.info("✓ Persistent browser session created - will parse all artists in one window")

            # Parse all artists using the same browser/page
            for idx, (artist_id, artist_name) in enumerate(artists, 1):
                logger.info(f"\n[{idx}/{len(artists)}] Processing: {artist_name} (ID: {artist_id})")

                try:
                    playlist_data = self._get_playlist_data(artist_id, artist_name, page)

                    logger.info(f"✓ Found: {playlist_data['count']} playlists ({playlist_data['total_likes']} total likes)")

                    # Update database
                    self.update_playlist_data(
                        artist_id,
                        today,
                        playlist_data['count'],
                        playlist_data['names'],
                        playlist_data['total_likes']
                    )

                    success_count += 1

                except Exception as e:
                    logger.error(f"✗ Failed to parse {artist_name}: {e}")
                    failed_count += 1

                # Delay before next request
                if idx < len(artists):
                    delay = random.uniform(delay_min, delay_max)
                    logger.info(f"⏱️  Waiting {delay:.1f} seconds before next request...")
                    time.sleep(delay)

            # Save cookies for next session
            self._save_cookies(context)

            # Close browser at the end
            browser.close()

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✓ Successfully parsed: {success_count}")
        logger.info(f"✗ Failed: {failed_count}")
        logger.info("=" * 60)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    from config import DB_PATH, HEADLESS

    logger.info("=" * 60)
    logger.info("Band.link Parser - Playlist Data Collector")
    logger.info("=" * 60)
    logger.info("")

    parser = BandLinkParser(db_path=DB_PATH, headless=HEADLESS)

    try:
        parser.parse_all()
    finally:
        parser.close()


if __name__ == '__main__':
    main()
