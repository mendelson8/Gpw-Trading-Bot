"""
News Monitor — polls Polish financial news and generates trading signals.

Supports two sources (configured via config.NEWS_SOURCE):
  - PAP RSS feed      (biznes.pap.pl/rss)
  - BiznesRadar.pl    (JSON API)

Each article is deduplicated, analysed by SentimentAnalyzer, and — if a
tradeable GPW ticker is identified — emits a BUY or SELL signal.
"""

import feedparser
import time
from datetime import datetime
import json
import requests
from bs4 import BeautifulSoup

import config
import notifications
from sentiment_analyzer import SentimentAnalyzer
from gpw_companies import is_ticker_tradeable, get_index_for_ticker


class NewsMonitor:
    """Monitors RSS / scraping sources and generates trading signals."""

    def __init__(self, rss_url, check_interval=60):
        self.rss_url = rss_url
        self.check_interval = check_interval
        self.seen_news_file = 'seen_news.json'
        self.seen_news = self._load_seen_news()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.signals = []
        self.signal_callback = None

        self.biznesradar_scraper = None
        if config.NEWS_SOURCE == "BIZNESRADAR":
            from biznesradar_scraper import BiznesRadarScraper
            self.biznesradar_scraper = BiznesRadarScraper()
            print(f"[INFO] News source: BiznesRadar.pl (scraping)")
        else:
            print(f"[INFO] News source: PAP RSS ({self.rss_url})")

    def set_signal_callback(self, callback):
        """Set a callback invoked immediately when a new signal is generated."""
        self.signal_callback = callback
        print("[INFO] Instant signal execution callback registered")

    def _load_seen_news(self):
        """Load the list of already-processed news IDs from file."""
        try:
            with open(self.seen_news_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def _save_seen_news(self):
        """Persist the seen-news set to file."""
        try:
            with open(self.seen_news_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_news), f, ensure_ascii=False, indent=2)
        except Exception as e:
            if config.VERBOSE_LOGGING:
                print(f"[WARNING] Failed to save seen_news: {e}")

    def send_notification(self, title, message, sound=True):
        """Send a desktop notification when notifications are available."""
        notifications.send_notification(title, message, sound)

    def fetch_article_content(self, url):
        """Fetch full article text (PAP or BiznesRadar)."""
        if "biznesradar.pl" in url and self.biznesradar_scraper:
            return self.biznesradar_scraper.fetch_article_content(url)
        else:
            return self._fetch_pap_article_content(url)

    def _fetch_pap_article_content(self, url):
        """Fetch full article text from biznes.pap.pl."""
        try:
            if config.VERBOSE_LOGGING:
                print(f"  Fetching full article content (PAP)...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            article = soup.find('article')

            if not article:
                if config.VERBOSE_LOGGING:
                    print(f"  <article> element not found in HTML")
                return None

            for unwanted in article.find_all(['script', 'style', 'nav', 'aside', 'footer',
                                             'div.advertisement', 'div.socialButtonsList']):
                unwanted.decompose()

            lead = article.find(class_='field--name-field-lead')
            lead_text = lead.get_text(strip=True) if lead else ""

            paragraphs = article.find_all('p')
            content_text = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

            full_text = f"{lead_text} {content_text}".strip()
            full_text = ' '.join(full_text.split())

            if len(full_text) > 3000:
                full_text = full_text[:3000] + "..."

            if config.VERBOSE_LOGGING:
                print(f"  Article fetched ({len(full_text)} chars)")

            return full_text if full_text else None

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching article: {e}")
            return None
        except Exception as e:
            print(f"  Error parsing article: {e}")
            return None

    def process_news_item(self, entry):
        """Analyse a single news item and generate a trading signal if warranted."""
        title = entry.get('title', 'No title')
        description = entry.get('description', '')
        link = entry.get('link', '')
        pub_date = entry.get('published', '')

        print(f"\n{'='*80}")
        print(f"NEW ARTICLE: {title}")
        print(f"Date: {pub_date}")
        print(f"Link: {link}")
        print("="*80)

        article_content = None
        if config.FETCH_FULL_ARTICLE:
            article_content = self.fetch_article_content(link)

        if article_content:
            description_for_ai = article_content
            if config.VERBOSE_LOGGING:
                print(f"[INFO] Using full article text ({len(description_for_ai)} chars)")
        else:
            description_for_ai = description
            if config.VERBOSE_LOGGING:
                print(f"[INFO] Using RSS description")

        sentiment, score, ai_ticker, justification = self.sentiment_analyzer.analyze(title, description_for_ai)

        ticker = ai_ticker

        print(f"Sentiment: {sentiment} (score: {score:.2f})")
        if justification:
            print(f"AI reasoning: {justification}")

        if ticker:
            print(f"Ticker: {ticker}")
        else:
            print("[INFO] No company ticker detected in article")

        if sentiment == 'POSITIVE' and score >= config.MIN_BUY_SENTIMENT_SCORE and ticker:
            self.send_notification(
                f"[BUY] {ticker}",
                f"Sentiment: {score:.1f}/5 | {title[:50]}..."
            )
        elif sentiment == 'NEGATIVE' and score < config.MIN_SELL_SENTIMENT_SCORE and ticker:
            self.send_notification(
                f"[SELL] {ticker}",
                f"Sentiment: {score:.1f}/5 | {title[:50]}..."
            )
        else:
            ticker_text = ticker if ticker else "No ticker"
            self.send_notification(
                f"[NEWS] {ticker_text}",
                f"{sentiment} ({score:.1f}) | {title[:50]}...",
                sound=False
            )

        signal = self.generate_signal(sentiment, score, ticker, title, link)
        if signal:
            self.signals.append(signal)
            self.save_signal(signal)

            if self.signal_callback and signal['action'] == 'BUY':
                print(f"[INFO] Triggering instant signal execution...")
                try:
                    self.signal_callback(signal)
                except Exception as e:
                    print(f"[ERROR] Callback error: {e}")

    def generate_signal(self, sentiment, score, ticker, news_title, news_link):
        """Generate a trading signal from the AI analysis result."""
        if not ticker:
            return None

        if not is_ticker_tradeable(ticker):
            index_name = get_index_for_ticker(ticker)
            if index_name:
                print(f"[INFO] {ticker} is in index {index_name} - OK")
            else:
                print(f"[REJECT] {ticker} is not in WIG20/mWIG40/sWIG80 - skipping signal")
                return None

        index_name = get_index_for_ticker(ticker)
        print(f"[INFO] {ticker} is in index {index_name}")

        if sentiment == 'POSITIVE' and score >= config.MIN_BUY_SENTIMENT_SCORE:
            signal = {
                'timestamp': datetime.now().isoformat(),
                'action': 'BUY',
                'ticker': ticker,
                'sentiment': sentiment,
                'score': score,
                'news_title': news_title,
                'news_link': news_link,
                'status': 'PENDING'
            }

            print(f"\n[SIGNAL] >>> BUY SIGNAL for {ticker} <<<")
            print(f"         Score: {score:.2f} | Article: {news_title[:60]}...")

            return signal

        elif sentiment == 'NEGATIVE' and score <= config.MIN_SELL_SENTIMENT_SCORE:
            signal = {
                'timestamp': datetime.now().isoformat(),
                'action': 'SELL',
                'ticker': ticker,
                'sentiment': sentiment,
                'score': score,
                'news_title': news_title,
                'news_link': news_link,
                'status': 'PENDING'
            }

            print(f"\n[SIGNAL] >>> SELL SIGNAL for {ticker} <<<")
            print(f"         Score: {score:.2f} | Article: {news_title[:60]}...")

            return signal

        else:
            print(f"[INFO] Sentiment too weak - no signal (score: {score:.2f}, required: >= {config.MIN_BUY_SENTIMENT_SCORE})")
            return None

    def save_signal(self, signal):
        """Append a signal to the trading_signals.json file."""
        signals_file = 'trading_signals.json'
        all_signals = []

        try:
            try:
                with open(signals_file, 'r', encoding='utf-8') as f:
                    all_signals = json.load(f)
            except FileNotFoundError:
                all_signals = []

            all_signals.append(signal)

            with open(signals_file, 'w', encoding='utf-8') as f:
                json.dump(all_signals, f, ensure_ascii=False, indent=2)

            print(f"[SAVE] Signal saved to {signals_file}")

        except Exception as e:
            print(f"[ERROR] Failed to save signal: {e}")

    def check_feed(self):
        """Fetch the news source and process new articles."""
        try:
            if config.VERBOSE_LOGGING:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking feed...")

            if config.NEWS_SOURCE == "BIZNESRADAR":
                entries = self._fetch_biznesradar_news()
            else:
                entries = self._fetch_pap_rss_news()

            new_items = 0

            for entry in entries:
                news_id = entry.get('id', entry.get('link', ''))

                if news_id in self.seen_news:
                    continue

                self.seen_news.add(news_id)
                self._save_seen_news()
                new_items += 1

                self.process_news_item(entry)

            if new_items == 0 and config.VERBOSE_LOGGING:
                print("[INFO] No new articles")
            elif new_items > 0:
                print(f"\n[INFO] Processed {new_items} new articles")

        except Exception as e:
            print(f"[ERROR] Error checking feed: {e}")

    def _fetch_pap_rss_news(self):
        """Fetch news from PAP RSS feed."""
        feed = feedparser.parse(self.rss_url)
        return feed.entries

    def _fetch_biznesradar_news(self):
        """Fetch news from BiznesRadar scraper."""
        if not self.biznesradar_scraper:
            print("[ERROR] BiznesRadar scraper not initialised")
            return []

        news_items = self.biznesradar_scraper.fetch_latest_news()

        entries = []
        for item in news_items:
            entries.append({
                'id': item.get('link', ''),
                'link': item.get('link', ''),
                'title': item.get('title', ''),
                'description': item.get('description', ''),
                'published': item.get('pub_date', '')
            })

        return entries

    def run(self):
        """Run the monitor in a loop."""
        print("="*80)
        print("NEWS MONITOR - Stock Market News Analysis")
        print("="*80)
        print(f"RSS Feed: {self.rss_url}")
        print(f"Interval: {self.check_interval}s")
        print(f"Min buy score: {config.MIN_BUY_SENTIMENT_SCORE}")
        print("="*80)

        try:
            iteration = 0
            while True:
                iteration += 1
                self.check_feed()

                if config.VERBOSE_LOGGING:
                    print(f"\n[INFO] Waiting {self.check_interval} seconds... (iteration #{iteration})")

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\n[INFO] Stopped by user")
            print(f"\n{'='*80}")
            print("STATISTICS")
            print("="*80)
            print(f"Signals generated: {len(self.signals)}")
            print(f"AI cost: ${self.sentiment_analyzer.total_cost:.4f}")
            print(f"Tokens used: {self.sentiment_analyzer.total_tokens:,}")
            print(f"Signals saved to: trading_signals.json")


def main():
    """Entry point."""
    monitor = NewsMonitor(config.RSS_URL, config.CHECK_INTERVAL)
    monitor.run()


if __name__ == "__main__":
    main()
