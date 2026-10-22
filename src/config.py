"""
Trading Bot — Configuration
All runtime settings are controlled from this file.
Secrets are loaded from .env (see .env.example).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / '.env')

NEWS_SOURCE = "BIZNESRADAR"
RSS_URL = "https://biznes.pap.pl/rss"
CHECK_INTERVAL = 60
FETCH_FULL_ARTICLE = True

BIZNESRADAR_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BIZNESRADAR_REQUEST_DELAY = (55, 65)
BIZNESRADAR_RETRY_DELAY = 30
BIZNESRADAR_MAX_RETRIES = 3

VERTEX_AI_API_KEY = os.environ.get('GOOGLE_API_KEY')
VERTEX_AI_MODEL = 'gemini-2.5-flash'

XTB_ENABLED = os.environ.get('XTB_ENABLED', 'false').lower() in {'1', 'true', 'yes'}

PYAUTOGUI_PAUSE = 1
PYAUTOGUI_FAILSAFE = True
SCREENSHOT_DIR = os.path.join(PROJECT_DIR, 'screenshots')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

XTB_DEFAULT_AMOUNT = 1000
XTB_SCREENSHOT_ON_TRADE = False
XTB_SELL_X_OFFSET = 1361

XTB_STOP_LOSS_PCT = -3.0
XTB_TRAILING_STOP_LOSS_PCT = 3.0
XTB_TAKE_PROFIT_PCT = 5.0
XTB_MAX_HOLDING_DAYS = 2
XTB_MAX_POSITIONS = 10
XTB_POSITIONS_STATE_FILE = 'xtb_positions_state.json'

MIN_BUY_SENTIMENT_SCORE = 4.0
MIN_SELL_SENTIMENT_SCORE = -2.0

VERBOSE_LOGGING = False
