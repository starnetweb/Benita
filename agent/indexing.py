"""
Google Indexing API — notifies Google to crawl a URL immediately after publishing.

Setup:
1. Enable "Web Search Indexing API" in Google Cloud Console
2. Create a Service Account and download the JSON key
3. Add the service account email as an Owner in Google Search Console
4. Set GOOGLE_INDEXING_CREDENTIALS in .env as the JSON key content (single line)
   OR set GOOGLE_INDEXING_KEY_FILE to the path of the JSON key file
"""
import json
import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

INDEXING_API = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES       = ["https://www.googleapis.com/auth/indexing"]


def _get_credentials():
    """Load Google service account credentials from env or file."""
    # Option 1: JSON content stored directly in env var
    creds_json = os.getenv("GOOGLE_INDEXING_CREDENTIALS", "").strip()
    if creds_json:
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError as e:
            logger.error(f"GOOGLE_INDEXING_CREDENTIALS is not valid JSON: {e}")
            return None

    # Option 2: Path to JSON key file
    key_file = os.getenv("GOOGLE_INDEXING_KEY_FILE", "").strip()
    if key_file and Path(key_file).exists():
        with open(key_file) as f:
            return json.load(f)

    return None


def _get_access_token(service_account_info: dict) -> str | None:
    """Exchange service account credentials for a Bearer token."""
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except ImportError:
        logger.error("google-auth not installed. Run: pip install google-auth")
        return None
    except Exception as e:
        logger.error(f"Failed to get Google access token: {e}")
        return None


def notify_google(url: str, url_type: str = "URL_UPDATED") -> bool:
    """
    Submit a URL to Google for immediate indexing.

    Args:
        url: The full URL of the published post
        url_type: "URL_UPDATED" (new/updated) or "URL_DELETED"

    Returns:
        True if successfully submitted, False otherwise
    """
    sa_info = _get_credentials()
    if not sa_info:
        logger.warning("Google Indexing API not configured — skipping. "
                       "Set GOOGLE_INDEXING_CREDENTIALS in .env to enable.")
        return False

    token = _get_access_token(sa_info)
    if not token:
        return False

    try:
        resp = requests.post(
            INDEXING_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"url": url, "type": url_type},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Google Indexing API: submitted {url} → "
                        f"notify_time={data.get('urlNotificationMetadata', {}).get('latestUpdate', {}).get('notifyTime', 'N/A')}")
            return True
        else:
            logger.warning(f"Google Indexing API returned {resp.status_code}: {resp.text[:300]}")
            return False

    except Exception as e:
        logger.error(f"Google Indexing API request failed: {e}")
        return False


def notify_google_batch(urls: list[str]) -> dict:
    """Submit multiple URLs at once. Returns {url: success}."""
    results = {}
    for url in urls:
        results[url] = notify_google(url)
    return results
