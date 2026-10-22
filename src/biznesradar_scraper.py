"""
BiznesRadar news client with request throttling and retry handling.
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json

import config


class BiznesRadarScraper:
    """Fetch and parse news articles from BiznesRadar.pl."""

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            'User-Agent': config.BIZNESRADAR_USER_AGENT,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-Requested-With': 'XMLHttpRequest',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })

        self.last_request_time = 0
        self.seen_articles_file = 'biznesradar_seen.json'
        self.seen_articles = self._load_seen_articles()
        self.current_referer = "https://www.biznesradar.pl/"
        self.request_count = 0

    def _load_seen_articles(self):
        """Load the list of already-processed articles from file."""
        try:
            with open(self.seen_articles_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def _save_seen_articles(self):
        """Persist the seen-articles set to file."""
        try:
            with open(self.seen_articles_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_articles), f, ensure_ascii=False, indent=2)
        except Exception as e:
            if config.VERBOSE_LOGGING:
                print(f"[WARNING] Failed to save biznesradar_seen: {e}")

    def _wait_before_request(self):
        """Apply a randomized delay between requests."""
        elapsed = time.time() - self.last_request_time

        min_delay, max_delay = config.BIZNESRADAR_REQUEST_DELAY
        required_delay = random.uniform(min_delay, max_delay)

        self.request_count += 1
        if self.request_count % 5 == 0:
            extra_delay = random.uniform(15, 30)
            required_delay += extra_delay
            if config.VERBOSE_LOGGING:
                print(f"[HTTP] Added request delay: {extra_delay:.1f}s")

        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            if config.VERBOSE_LOGGING:
                print(f"[HTTP] Waiting {wait_time:.1f}s before the next request")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def _fetch_with_retry(self, url, max_retries=None, referer=None):
        """Fetch a URL with retry and exponential backoff."""
        if max_retries is None:
            max_retries = config.BIZNESRADAR_MAX_RETRIES

        for attempt in range(max_retries):
            try:
                self._wait_before_request()

                headers = {}
                if referer:
                    headers['Referer'] = referer
                    self.current_referer = url

                response = self.session.get(url, timeout=15, headers=headers)
                if response.status_code == 200:
                    if config.VERBOSE_LOGGING:
                        print("[HTTP] Request succeeded")
                    return response

                elif response.status_code in [403, 429]:
                    retry_delay = config.BIZNESRADAR_RETRY_DELAY * (2 ** attempt)
                    print(f"[HTTP] Status {response.status_code}; retrying in {retry_delay}s ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue

                else:
                    print(f"[HTTP] Status {response.status_code}: {url}")
                    return None

            except requests.exceptions.RequestException as e:
                print(f"[HTTP] Connection error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None

        print(f"[HTTP] Request failed after {max_retries} attempts: {url}")
        return None

    def fetch_latest_news(self):
        """Fetch the latest news from the BiznesRadar JSON API."""
        api_url = "https://www.biznesradar.pl/news-current-json/"

        print(f"[SCRAPER] Fetching news from BiznesRadar API...")

        referer = "https://www.biznesradar.pl/news/1"

        response = self._fetch_with_retry(api_url, referer=referer)
        if not response:
            print(f"[SCRAPER] Failed to fetch API")
            return []

        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"[SCRAPER] Response is not valid JSON")
            print(f"[SCRAPER] First 200 chars: {response.text[:200]}")
            return []

        if config.VERBOSE_LOGGING:
            print(f"[SCRAPER] Received JSON with {len(data) if isinstance(data, list) else 'N/A'} items")

        news_items = []

        if not isinstance(data, list):
            print(f"[SCRAPER] Unexpected format - expected list, got: {type(data)}")
            return []

        for item in data:
            try:
                title = item.get('targetName', '')
                link = item.get('targetUrl', '')
                pub_date = item.get('datetime', '')
                description = item.get('body', '')

                if not title or not link:
                    continue

                news_items.append({
                    'title': title,
                    'link': link,
                    'pub_date': pub_date,
                    'description': description
                })
            except Exception as e:
                if config.VERBOSE_LOGGING:
                    print(f"[SCRAPER] Error parsing news item: {e}")
                continue

        print(f"[SCRAPER] Parsed {len(news_items)} news items")
        return news_items

    def fetch_article_content(self, article_url):
        """Fetch the full text of an article from BiznesRadar."""
        referer = "https://www.biznesradar.pl/news/1"

        response = self._fetch_with_retry(article_url, referer=referer)

        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        article_body = soup.find('div', class_='article-body')

        if not article_body:
            article_body = soup.find('article')

        if not article_body:
            article_body = soup.find('div', id=lambda x: x and 'article' in x.lower())

        if not article_body:
            if config.VERBOSE_LOGGING:
                print(f"[SCRAPER] Article body not found in HTML")
            return None

        for unwanted in article_body.find_all(['script', 'style', 'iframe', 'aside', 'div.ad']):
            unwanted.decompose()

        paragraphs = article_body.find_all('p')
        text = ' '.join([p.get_text(strip=True) for p in paragraphs])

        if not text:
            text = article_body.get_text(separator=' ', strip=True)

        if len(text) > 3000:
            text = text[:3000] + "..."

        if config.VERBOSE_LOGGING:
            print(f"[SCRAPER] Article fetched ({len(text)} chars)")

        return text if text else None

