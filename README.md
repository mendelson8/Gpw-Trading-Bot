# GPW News Trading Bot

A Python prototype that turns Polish financial news into sentiment signals and can execute trades in an XTB xStation 5 demo account. It combines news collection, company and ticker matching, Gemini-based sentiment analysis, OCR, and desktop automation.

This is an experimental portfolio project. The trading path depends on screen coordinates and OCR, so it should be run against a demo account with the trading interface visible.

## Workflow

```text
PAP RSS / BiznesRadar
        ↓
News collection and deduplication
        ↓
Gemini sentiment analysis and GPW ticker matching
        ↓
Signal generation
        ↓
Optional XTB demo execution and position monitoring
```

## Features

- PAP RSS and BiznesRadar news sources, with article text extraction
- Sentiment scores from -5 to +5 and GPW ticker identification
- Persistent article deduplication and signal records
- XTB xStation 5 demo order automation using PyAutoGUI
- Position monitoring with stop loss, trailing stop, take profit, and holding-period rules
- OCR-based position reading with EasyOCR and Tesseract
- UI coordinate calibration for the local screen

## Project layout

```text
.
├── src/
│   ├── main.py                 # Application entry point
│   ├── config.py               # Runtime settings and environment variables
│   ├── sentiment_analyzer.py   # Gemini sentiment analysis
│   ├── news_monitor.py         # News polling, deduplication, and signals
│   ├── biznesradar_scraper.py  # BiznesRadar news client
│   ├── gpw_companies.py        # GPW company and ticker mapping
│   ├── xtb_trader.py           # XTB UI automation and OCR
│   ├── xtb_coordinates.py      # Local xStation UI coordinates
│   ├── calibrate_xtb.py        # Coordinate calibration utility
│   └── notifications.py        # Optional macOS notifications
├── requirements.txt
├── .env.example
└── .gitignore
```

Runtime state and screenshots are generated locally and ignored by Git.

## Requirements

- Python 3.11 or newer
- macOS for the configured desktop automation and notifications
- Tesseract OCR available on `PATH`
- Google Gemini API key
- XTB demo account and an open xStation 5 browser window

EasyOCR is optional; Tesseract is the fallback OCR engine.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add your Gemini API key to `.env`:

```dotenv
GOOGLE_API_KEY=your_google_ai_api_key
```

Before using the trading interface, calibrate the coordinates for your display:

```bash
python src/calibrate_xtb.py
```

Start the application from the repository root:

```bash
python src/main.py
```

XTB screen automation is disabled by default. Set `XTB_ENABLED=true` in `.env` to enable demo trading. Log in to xStation manually before starting the bot.

## Configuration

The main thresholds and polling settings are in `src/config.py`:

| Setting | Default | Purpose |
|---|---:|---|
| `XTB_ENABLED` | `false` | Opt in to XTB demo screen automation |
| `CHECK_INTERVAL` | 60 seconds | News and position polling interval |
| `MIN_BUY_SENTIMENT_SCORE` | 4.0 | Minimum score for a buy signal |
| `MIN_SELL_SENTIMENT_SCORE` | -2.0 | Score that can trigger a sell signal |
| `XTB_DEFAULT_AMOUNT` | 1000 PLN | Default order size |
| `XTB_STOP_LOSS_PCT` | -3.0% | Position loss threshold |
| `XTB_TRAILING_STOP_LOSS_PCT` | 3.0% | Allowed fall from peak profit |
| `XTB_TAKE_PROFIT_PCT` | 5.0% | Profit target |
| `XTB_MAX_HOLDING_DAYS` | 2 days | Maximum position age |
| `XTB_MAX_POSITIONS` | 10 | Maximum open positions |

## Limitations

- The XTB integration uses screen automation rather than a supported trading API.
- OCR results and UI coordinates can be affected by screen resolution, scaling, layout changes, or overlays.
- The project has not been validated for live trading; use a demo account only.
- Gemini API access requires a valid API key and may incur usage costs.
