"""
WordPress REST API poster with Yoast SEO field support.
"""
import json
import logging
import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

WP_SITE_URL = os.getenv("WP_SITE_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
WP_POST_STATUS = os.getenv("WP_POST_STATUS", "draft")
WP_DEFAULT_CATEGORY = int(os.getenv("WP_DEFAULT_CATEGORY_ID", "1"))
WP_DEFAULT_AUTHOR = int(os.getenv("WP_DEFAULT_AUTHOR_ID", "1"))

API_BASE = f"{WP_SITE_URL}/wp-json/wp/v2"


def _auth():
    return (WP_USERNAME, WP_APP_PASSWORD)


def _headers():
    return {"Content-Type": "application/json"}


def _clean_html(html: str) -> str:
    """Replace [IMAGE: ...] and [INTERNAL_LINK: ...] placeholders with clean HTML."""
    # Replace image placeholders with a WordPress block comment (editor will fill)
    html = re.sub(
        r'\[IMAGE: ([^\]]+)\]',
        r'<!-- wp:image --><figure class="wp-block-image"><img alt="\1" /></figure><!-- /wp:image -->',
        html
    )
    # Replace internal link placeholders with a styled span for easy editorial follow-up
    html = re.sub(
        r'\[INTERNAL_LINK: ([^\]]+)\]',
        r'<a href="#" class="internal-link-placeholder" data-topic="\1">\1</a>',
        html
    )
    return html


def get_or_create_tag(tag_name: str) -> int | None:
    """Return tag ID, creating it if needed."""
    try:
        resp = requests.get(
            f"{API_BASE}/tags",
            params={"search": tag_name, "per_page": 1},
            auth=_auth(), timeout=10
        )
        data = resp.json()
        if data:
            return data[0]["id"]
        # Create
        r = requests.post(
            f"{API_BASE}/tags",
            json={"name": tag_name, "slug": tag_name.lower().replace(" ", "-")},
            auth=_auth(), headers=_headers(), timeout=10
        )
        return r.json().get("id")
    except Exception as e:
        logger.warning(f"Tag '{tag_name}' error: {e}")
        return None


def get_or_create_category(cat_name: str) -> int:
    """Return category ID, creating it if needed."""
    try:
        resp = requests.get(
            f"{API_BASE}/categories",
            params={"search": cat_name, "per_page": 1},
            auth=_auth(), timeout=10
        )
        data = resp.json()
        if data:
            return data[0]["id"]
        r = requests.post(
            f"{API_BASE}/categories",
            json={"name": cat_name, "slug": cat_name.lower().replace(" ", "-")},
            auth=_auth(), headers=_headers(), timeout=10
        )
        return r.json().get("id", WP_DEFAULT_CATEGORY)
    except Exception as e:
        logger.warning(f"Category '{cat_name}' error: {e}")
        return WP_DEFAULT_CATEGORY


def build_schema_script(schema: dict) -> str:
    """Wrap schema in a JSON-LD script tag for insertion into post content."""
    return (
        '\n<script type="application/ld+json">\n'
        + json.dumps(schema, indent=2, ensure_ascii=False)
        + '\n</script>\n'
    )


def post_to_wordpress(post_data: dict) -> dict:
    """
    Publish a blog post to WordPress.
    post_data keys: seo_title, focus_keyphrase, meta_description, slug,
                    content_html, schema_markup, tags, categories, excerpt
    Returns dict with wp_post_id and wp_url.
    """
    if not WP_SITE_URL or not WP_USERNAME or not WP_APP_PASSWORD:
        raise ValueError("WordPress credentials not configured in .env")

    content = _clean_html(post_data.get("content_html", ""))

    # Append schema JSON-LD to post content
    schema = post_data.get("schema_markup")
    if schema:
        content += build_schema_script(schema)

    # Resolve tag IDs
    tag_ids = []
    for tag in (post_data.get("tags") or [])[:10]:
        clean_tag = str(tag).lstrip("#").strip()
        if not clean_tag:
            continue
        tid = get_or_create_tag(clean_tag)
        if tid:
            tag_ids.append(tid)

    # Resolve category IDs
    cat_ids = [WP_DEFAULT_CATEGORY]
    for cat in (post_data.get("categories") or []):
        cid = get_or_create_category(str(cat))
        if cid and cid not in cat_ids:
            cat_ids.append(cid)

    payload = {
        "title": post_data.get("seo_title", ""),
        "content": content,
        "excerpt": post_data.get("excerpt", ""),
        "slug": post_data.get("slug", ""),
        "status": WP_POST_STATUS,
        "author": WP_DEFAULT_AUTHOR,
        "categories": cat_ids,
        "tags": tag_ids,
        "meta": {
            "_yoast_wpseo_title":                 post_data.get("seo_title", ""),
            "_yoast_wpseo_metadesc":              post_data.get("meta_description", ""),
            "_yoast_wpseo_focuskw":               post_data.get("focus_keyphrase", ""),
            "_yoast_wpseo_opengraph-title":       post_data.get("seo_title", ""),
            "_yoast_wpseo_opengraph-description": post_data.get("meta_description", ""),
        },
    }

    logger.info(f"Posting to WordPress: '{payload['title'][:60]}'")

    try:
        resp = requests.post(
            f"{API_BASE}/posts",
            json=payload,
            auth=_auth(),
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        wp_id = result.get("id")
        wp_url = result.get("link", "")
        logger.info(f"Published! WP Post ID: {wp_id} â€” {wp_url}")
        return {"wp_post_id": wp_id, "wp_url": wp_url}

    except requests.HTTPError as e:
        err_body = e.response.text[:500] if e.response else str(e)
        logger.error(f"WordPress API error: {e} â€” {err_body}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error posting to WP: {e}")
        raise


def test_wp_connection() -> bool:
    """Test WordPress API connectivity and return True if OK."""
    try:
        resp = requests.get(
            f"{API_BASE}/users/me",
            auth=_auth(), timeout=10
        )
        if resp.status_code == 200:
            user = resp.json()
            logger.info(f"WP connected as: {user.get('name', 'unknown')}")
            return True
        logger.error(f"WP connection failed: HTTP {resp.status_code}")
        return False
    except Exception as e:
        logger.error(f"WP connection error: {e}")
        return False
