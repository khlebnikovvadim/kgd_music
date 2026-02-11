"""
Configuration file for Yandex Music Parser
"""

# Proxy settings (set to None if not using proxy)
# Format: 'http://username:password@host:port' or 'http://host:port'
PROXY_SERVER = None  # Example: 'http://proxy.example.com:8080'

# Proxy with authentication example:
# PROXY_SERVER = 'http://user:pass@proxy.example.com:8080'

# For SOCKS5 proxy:
# PROXY_SERVER = 'socks5://proxy.example.com:1080'

# Browser settings
HEADLESS = True  # Run browser in background (no window)

# Delay settings (seconds between requests)
DELAY_MIN = 5
DELAY_MAX = 10

# Database path
DB_PATH = 'data/artists.db'

# CSV export path
CSV_PATH = 'data/artist_stats.csv'

# Timeout settings (milliseconds)
PAGE_TIMEOUT = 30000
WAIT_AFTER_LOAD = 5000  # Wait after page loads for JS to execute
