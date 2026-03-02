"""
Configuration file for Yandex Music Parser
"""

# Proxy settings
# Set to None if running from Russia (no proxy needed!)
# Only needed if running from outside Russia/CIS
PROXY_SERVER = None

# Examples (only if you need proxy):
# PROXY_SERVER = 'http://proxy.example.com:8080'
# PROXY_SERVER = 'http://user:pass@proxy.example.com:8080'  # with auth
# PROXY_SERVER = 'socks5://proxy.example.com:1080'  # SOCKS5

# Browser settings
HEADLESS = False  # Run browser in headful mode (better for avoiding detection, window auto-minimizes)

# Delay settings (seconds between requests)
DELAY_MIN = 15
DELAY_MAX = 25

# Database path
DB_PATH = 'data/artists.db'

# CSV export path
CSV_PATH = 'data/artist_stats.csv'

# Timeout settings (milliseconds)
PAGE_TIMEOUT = 30000
WAIT_AFTER_LOAD = 5000  # Wait after page loads for JS to execute
