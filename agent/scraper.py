"""
News scraper: Google News RSS, Nigerian news sites, Twitter/X.
"""
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fake_useragent import UserAgent

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

try:
    ua = UserAgent()
    _UA = ua.random
except Exception:
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "168"))  # 7 days â€” Google News dates are unreliable

# Keywords that qualify an article as JAMB/admission related
JAMB_KEYWORDS = [
    "jamb", "utme", "post-utme", "post utme", "admission", "matriculation",
    "university admission", "polytechnic", "waec", "neco", "ssce", "a-level",
    "screening", "cut-off", "cutoff", "supplementary", "clearance", "registration",
    "result checker", "caps", "central admission", "de registration",
]


def _is_recent(pub_date_str: Optional[str]) -> bool:
    """Return True if the article was published within the lookback window."""
    if not pub_date_str:
        return True  # assume recent if no date
    try:
        import email.utils
        parsed = email.utils.parsedate_to_datetime(pub_date_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        return parsed >= cutoff
    except Exception:
        return True


def _is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in JAMB_KEYWORDS)


def _make_hash(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()


def _fetch_full_content(url: str, timeout: int = 15) -> str:
    """Scrape article body text from a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "iframe", "noscript", "ads"]):
            tag.decompose()

        # Try common article containers
        content = None
        for sel in ["article", ".post-content", ".entry-content",
                    ".article-body", ".story-body", "main"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 200:
                content = el
                break

        if not content:
            content = soup.find("body") or soup

        paragraphs = content.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
        return text[:8000]  # cap at 8k chars
    except Exception as e:
        logger.warning(f"Could not fetch full content from {url}: {e}")
        return ""


# â”€â”€ RSS Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_rss(source: dict) -> list[dict]:
    """Fetch articles from an RSS feed."""
    results = []
    url = source.get("url")
    if not url:
        return results

    try:
        feed = feedparser.parse(url)
        logger.info(f"[RSS] {source['name']}: {len(feed.entries)} entries")

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip()
            pub   = getattr(entry, "published", None) or getattr(entry, "updated", None)
            summary = BeautifulSoup(
                entry.get("summary", ""), "lxml"
            ).get_text(strip=True)[:1000]

            # Skip blank or irrelevant titles
            # NOTE: we do NOT filter by date â€” Google News dates are unreliable.
            # Hash-based deduplication in the DB prevents reposting the same article.
            if not title or not _is_relevant(title, summary):
                continue

            # Fetch full content
            time.sleep(1)
            full_content = _fetch_full_content(link) if link else summary

            results.append({
                "source_id": source["id"],
                "title": title,
                "url": link,
                "summary": summary,
                "full_content": full_content or summary,
                "author": entry.get("author", ""),
                "published_at": pub,
                "hash": _make_hash(link, title),
            })

    except Exception as e:
        logger.error(f"[RSS] Error scraping {source['name']}: {e}")

    return results


# â”€â”€ Twitter/X Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_twitter_api(handle_or_hashtag: str, is_hashtag: bool = False) -> list[dict]:
    """Fetch tweets via Twitter API v2 using tweepy."""
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer:
        logger.info("[Twitter] No bearer token â€” skipping API fetch")
        return []

    try:
        import tweepy
        client = tweepy.Client(bearer_token=bearer, wait_on_rate_limit=True)

        if is_hashtag:
            query = f"#{handle_or_hashtag} -is:retweet lang:en"
        else:
            query = f"from:{handle_or_hashtag} -is:retweet"

        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        response = client.search_recent_tweets(
            query=query,
            start_time=cutoff,
            max_results=20,
            tweet_fields=["created_at", "author_id", "text", "entities"],
            expansions=["author_id"],
        )

        if not response.data:
            return []

        results = []
        for tweet in response.data:
            text = tweet.text
            if not _is_relevant(text):
                continue

            # Extract URLs from tweet
            urls = []
            if tweet.entities and "urls" in tweet.entities:
                urls = [u["expanded_url"] for u in tweet.entities["urls"]
                        if "twitter.com" not in u.get("expanded_url", "")]

            full_content = ""
            if urls:
                time.sleep(1)
                full_content = _fetch_full_content(urls[0])

            results.append({
                "source_id": None,
                "title": text[:200],
                "url": urls[0] if urls else f"https://twitter.com/i/web/status/{tweet.id}",
                "summary": text,
                "full_content": full_content or text,
                "author": handle_or_hashtag,
                "published_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "hash": _make_hash(str(tweet.id), text[:100]),
            })
        return results

    except Exception as e:
        logger.error(f"[Twitter API] Error for {handle_or_hashtag}: {e}")
        return []


def scrape_twitter_nitter(handle_or_hashtag: str, is_hashtag: bool = False) -> list[dict]:
    """Fallback: scrape via public Nitter instances."""
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
    ]

    for base in nitter_instances:
        try:
            if is_hashtag:
                url = f"{base}/search?f=tweets&q=%23{handle_or_hashtag}&since_time=86400"
            else:
                url = f"{base}/{handle_or_hashtag}"

            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            results = []

            for tweet_div in soup.select(".timeline-item")[:20]:
                content_el = tweet_div.select_one(".tweet-content")
                if not content_el:
                    continue
                text = content_el.get_text(strip=True)

                if not _is_relevant(text):
                    continue

                date_el = tweet_div.select_one(".tweet-date a")
                link_el = tweet_div.select_one(".tweet-link")
                tweet_url = urljoin(base, link_el["href"]) if link_el else ""
                pub = date_el["title"] if date_el else None

                results.append({
                    "source_id": None,
                    "title": text[:200],
                    "url": tweet_url,
                    "summary": text,
                    "full_content": text,
                    "author": handle_or_hashtag,
                    "published_at": pub,
                    "hash": _make_hash(tweet_url, text[:100]),
                })

            if results:
                logger.info(f"[Nitter] Got {len(results)} tweets from {base}")
                return results

        except Exception as e:
            logger.warning(f"[Nitter] {base} failed: {e}")
            continue

    return []


def scrape_twitter_source(source: dict) -> list[dict]:
    handle = source.get("handle", "")
    is_hashtag = source.get("type") == "twitter_hashtag"
    results = scrape_twitter_api(handle, is_hashtag)
    if not results:
        results = scrape_twitter_nitter(handle, is_hashtag)
    for r in results:
        r["source_id"] = source["id"]
    return results


# â”€â”€ Main Entry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_all_sources(sources: list[dict]) -> list[dict]:
    """Scrape all active sources and return raw article dicts."""
    all_articles = []

    for source in sources:
        stype = source.get("type", "rss")
        logger.info(f"Scraping source: {source['name']} [{stype}]")

        if stype == "rss":
            articles = scrape_rss(source)
        elif stype in ("twitter", "twitter_hashtag"):
            articles = scrape_twitter_source(source)
        else:
            logger.warning(f"Unknown source type: {stype}")
            continue

        logger.info(f"  >> {len(articles)} relevant articles")
        all_articles.extend(articles)
        time.sleep(2)  # polite delay between sources

    logger.info(f"Total articles scraped: {len(all_articles)}")
    return all_articles
