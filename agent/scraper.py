"""
News scraper: Tavily Search API (primary) + RSS fallback.
Tavily returns full article content — no HTML scraping needed.
"""
import hashlib
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

LOOKBACK_DAYS = int(os.getenv("NEWS_LOOKBACK_HOURS", "168")) // 24 or 7  # Tavily uses days

# ── JAMB search queries for Tavily ───────────────────────────────────────────
TAVILY_QUERIES = [
    "JAMB UTME 2025 2026 latest news Nigeria",
    "JAMB admission screening Nigeria universities 2025 2026",
    "Post-UTME form screening date Nigeria 2025 2026",
    "JAMB cut-off mark 2025 2026 university admission",
    "JAMB result checker 2025 UTME scores Nigeria",
    "WAEC NECO SSCE result 2025 Nigeria admission",
    "JAMB registration deadline CAPS direct entry 2025 2026",
    "Nigerian university polytechnic admission list 2025 2026",
    "JAMB supplementary admission clearance 2025",
    "UTME subject combination requirements Nigeria universities",
]

# Keywords to confirm JAMB relevance
JAMB_KEYWORDS = [
    "jamb", "utme", "post-utme", "post utme", "admission", "matriculation",
    "university admission", "polytechnic", "waec", "neco", "ssce",
    "screening", "cut-off", "cutoff", "supplementary", "clearance",
    "caps", "central admission", "direct entry", "nigeria", "federal university",
]


def _make_hash(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()


def _is_relevant(title: str, content: str = "") -> bool:
    text = (title + " " + content[:500]).lower()
    return any(kw in text for kw in JAMB_KEYWORDS)


# ── Tavily Scraper ────────────────────────────────────────────────────────────

def scrape_tavily(max_results_per_query: int = 5) -> list[dict]:
    """
    Search for JAMB news via Tavily API.
    Returns articles with full content — no additional scraping needed.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("[Tavily] TAVILY_API_KEY not set — skipping Tavily search")
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
    except ImportError:
        logger.error("[Tavily] tavily-python not installed. Run: pip install tavily-python")
        return []

    all_results = []
    seen_urls = set()

    for query in TAVILY_QUERIES:
        try:
            logger.info(f"[Tavily] Searching: {query}")
            response = client.search(
                query=query,
                search_depth="advanced",
                topic="news",
                days=LOOKBACK_DAYS,
                max_results=max_results_per_query,
                include_raw_content=True,   # get full article text
            )

            results = response.get("results", [])
            logger.info(f"[Tavily] Got {len(results)} results for: {query[:50]}")

            for r in results:
                url   = r.get("url", "")
                title = r.get("title", "").strip()

                if not url or not title:
                    continue
                if url in seen_urls:
                    continue
                if not _is_relevant(title, r.get("content", "")):
                    continue

                seen_urls.add(url)

                # Tavily provides raw_content (full article) or content (snippet)
                full_content = (r.get("raw_content") or r.get("content") or "").strip()
                summary      = r.get("content", "")[:1000]
                pub_date     = r.get("published_date", "")

                all_results.append({
                    "source_id": None,   # Tavily results have no DB source row
                    "title":        title,
                    "url":          url,
                    "summary":      summary,
                    "full_content": full_content or summary,
                    "author":       r.get("author", ""),
                    "published_at": pub_date,
                    "hash":         _make_hash(url, title),
                    "score":        r.get("score", 0),
                })

            time.sleep(1)   # polite delay between queries

        except Exception as e:
            logger.error(f"[Tavily] Error for query '{query[:50]}': {e}")
            continue

    # Sort by relevance score (highest first)
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    logger.info(f"[Tavily] Total unique relevant articles: {len(all_results)}")
    return all_results


# ── RSS Fallback ─────────────────────────────────────────────────────────────

def _fetch_full_content(url: str, timeout: int = 15) -> str:
    """Scrape article body text from a URL (used for RSS fallback)."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        content = None
        for sel in ["article", ".post-content", ".entry-content", ".article-body", "main"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 200:
                content = el
                break
        if not content:
            content = soup.find("body") or soup
        paragraphs = content.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
        return text[:8000]
    except Exception as e:
        logger.warning(f"Could not fetch content from {url}: {e}")
        return ""


def scrape_rss(source: dict) -> list[dict]:
    """RSS fallback: used when TAVILY_API_KEY is not set."""
    results = []
    url = source.get("url", "")
    if not url:
        return results
    try:
        feed = feedparser.parse(url)
        logger.info(f"[RSS] {source['name']}: {len(feed.entries)} entries")
        for entry in feed.entries:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "").strip()
            pub     = getattr(entry, "published", None) or getattr(entry, "updated", None)
            summary = BeautifulSoup(entry.get("summary", ""), "lxml").get_text(strip=True)[:1000]
            if not title or not _is_relevant(title, summary):
                continue
            time.sleep(1)
            full_content = _fetch_full_content(link) if link else summary
            results.append({
                "source_id":    source["id"],
                "title":        title,
                "url":          link,
                "summary":      summary,
                "full_content": full_content or summary,
                "author":       entry.get("author", ""),
                "published_at": pub,
                "hash":         _make_hash(link, title),
            })
    except Exception as e:
        logger.error(f"[RSS] Error scraping {source['name']}: {e}")
    return results


# ── Main Entry ────────────────────────────────────────────────────────────────

def scrape_all_sources(sources: list[dict]) -> list[dict]:
    """
    Primary: Tavily API search (all JAMB queries).
    Fallback: RSS feeds from DB sources (if Tavily key not set).
    """
    tavily_key = os.getenv("TAVILY_API_KEY", "")

    if tavily_key:
        # ── Tavily mode ───────────────────────────────────────────────────────
        logger.info("[Scraper] Using Tavily API for news search")
        all_articles = scrape_tavily()

        # Also run Tavily searches using source names as extra queries
        source_names = [s["name"] for s in sources if s.get("type") == "rss"]
        if source_names:
            seen_urls = {a["url"] for a in all_articles}
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=tavily_key)
                for name in source_names[:5]:   # limit to 5 extra source queries
                    query = f"{name} JAMB admission Nigeria 2025 2026"
                    try:
                        resp = client.search(
                            query=query,
                            search_depth="basic",
                            topic="news",
                            days=LOOKBACK_DAYS,
                            max_results=3,
                            include_raw_content=True,
                        )
                        for r in resp.get("results", []):
                            url   = r.get("url", "")
                            title = r.get("title", "").strip()
                            if url and title and url not in seen_urls and _is_relevant(title, r.get("content", "")):
                                seen_urls.add(url)
                                full_content = (r.get("raw_content") or r.get("content") or "").strip()
                                all_articles.append({
                                    "source_id":    None,
                                    "title":        title,
                                    "url":          url,
                                    "summary":      r.get("content", "")[:1000],
                                    "full_content": full_content,
                                    "author":       r.get("author", ""),
                                    "published_at": r.get("published_date", ""),
                                    "hash":         _make_hash(url, title),
                                    "score":        r.get("score", 0),
                                })
                        time.sleep(1)
                    except Exception as e:
                        logger.warning(f"[Tavily] Source query failed for {name}: {e}")
            except ImportError:
                pass

    else:
        # ── RSS fallback mode ─────────────────────────────────────────────────
        logger.info("[Scraper] Tavily key not set — falling back to RSS feeds")
        all_articles = []
        for source in sources:
            stype = source.get("type", "rss")
            logger.info(f"Scraping source: {source['name']} [{stype}]")
            if stype == "rss":
                articles = scrape_rss(source)
            else:
                logger.warning(f"Skipping source type '{stype}' in RSS fallback mode")
                articles = []
            logger.info(f"  >> {len(articles)} relevant articles")
            all_articles.extend(articles)
            time.sleep(2)

    logger.info(f"[Scraper] Total articles fetched: {len(all_articles)}")
    return all_articles
