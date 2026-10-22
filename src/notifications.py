"""
Notifications — macOS desktop alerts via pync.

Sends a native macOS notification for every buy/sell signal so you can
monitor the bot while the terminal is in the background.
Gracefully no-ops on non-macOS systems or when pync is not installed.
"""

import platform

IS_MACOS = platform.system() == 'Darwin'

if IS_MACOS:
    try:
        import pync
        NOTIFICATIONS_AVAILABLE = True
    except ImportError:
        print("[WARNING] pync library is not installed. Notifications disabled.")
        print("          Install: pip install pync")
        NOTIFICATIONS_AVAILABLE = False
else:
    NOTIFICATIONS_AVAILABLE = False
    print("[INFO] Notifications are only available on macOS")


def send_notification(title, message, sound=True):
    """Send a system notification (macOS)."""
    if not NOTIFICATIONS_AVAILABLE:
        return

    try:
        if sound:
            pync.notify(message, title=title, sound='default')
        else:
            pync.notify(message, title=title)
    except Exception as e:
        print(f"[WARNING] Failed to send notification: {e}")


def notify_news_analyzed(ticker, sentiment, score, news_title):
    """Send a notification for an analysed news article."""
    prefix = {
        'POSITIVE': '[BUY]',
        'NEGATIVE': '[SELL]',
        'NEUTRAL':  '[NEUTRAL]'
    }.get(sentiment, '[NEWS]')

    if ticker:
        title = f"{prefix} {ticker}: {sentiment}"
    else:
        title = f"{prefix} News: {sentiment}"

    message = f"Score: {score:+.2f}\n{news_title[:80]}"
    send_notification(title, message, sound=(abs(score) >= 4))


def notify_buy(ticker, amount, score):
    """Send a notification for a buy order."""
    title = f"[BUY] {ticker}"
    message = f"Amount: {amount} PLN | Sentiment: {score:+.2f}"
    send_notification(title, message, sound=True)


def notify_sell(ticker, reason, profit_pct=None):
    """Send a notification for a sell order."""
    title = f"[SELL] {ticker}"

    if profit_pct is not None:
        message = f"Profit: {profit_pct:+.2f}% | {reason}"
    else:
        message = reason

    send_notification(title, message, sound=True)


def notify_error(message):
    """Send an error notification."""
    title = "[ERROR] Bot"
    send_notification(title, message, sound=True)


def notify_bot_status(message):
    """Send a bot status notification."""
    title = "[BOT] Trading Bot"
    send_notification(title, message, sound=False)
