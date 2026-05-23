"""
Post all unposted DB drafts to WordPress.
Usage: python post_drafts.py [--category "Admission News"] [--status publish]
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Force UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(Path(__file__).parent.parent / "logs" / "agent.log"),
                            encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("post_drafts")

sys.path.insert(0, str(Path(__file__).parent))
import db
import wp_poster


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="Admission News",
                        help="WordPress category name (default: Admission News)")
    parser.add_argument("--status", default="draft",
                        choices=["draft", "publish"],
                        help="Post status (default: draft)")
    args = parser.parse_args()

    # Override WP_POST_STATUS for this run
    os.environ["WP_POST_STATUS"] = args.status
    # Reload wp_poster settings
    import importlib
    importlib.reload(wp_poster)

    # Test WP connection
    logger.info("Testing WordPress connection...")
    if not wp_poster.test_wp_connection():
        logger.error("Cannot reach WordPress. Check your .env credentials.")
        sys.exit(1)

    # Get or create the target category
    logger.info(f"Resolving category: '{args.category}'")
    cat_id = wp_poster.get_or_create_category(args.category)
    logger.info(f"Category ID: {cat_id}")

    # Fetch all DB posts not yet pushed to WP
    conn = db.get_conn()
    pending = conn.execute(
        "SELECT * FROM posts WHERE status='draft' AND (wp_post_id IS NULL OR wp_post_id=0) ORDER BY id"
    ).fetchall()
    conn.close()

    if not pending:
        logger.info("No pending draft posts found in database.")
        return

    logger.info(f"Found {len(pending)} post(s) to publish.")

    ok = 0
    fail = 0
    for row in pending:
        post = dict(row)
        logger.info(f"Posting: [{post['id']}] {post['title'][:70]}")

        # Rebuild post_data dict from DB columns
        schema = None
        if post.get("schema_markup"):
            try:
                schema = json.loads(post["schema_markup"])
            except Exception:
                schema = None

        post_data = {
            "seo_title":        post["title"],
            "focus_keyphrase":  post.get("focus_keyphrase", ""),
            "meta_description": post.get("meta_description", ""),
            "slug":             post.get("slug", ""),
            "content_html":     post.get("content", ""),
            "schema_markup":    schema,
            "excerpt":          post.get("meta_description", "")[:160],
            "tags":             [],
            "categories":       [args.category],
        }

        # Inject the resolved category ID directly so wp_poster uses it
        try:
            import requests
            api_base = wp_poster.API_BASE

            content = wp_poster._clean_html(post_data.get("content_html", ""))
            if schema:
                content += wp_poster.build_schema_script(schema)

            payload = {
                "title":      post_data["seo_title"],
                "content":    content,
                "excerpt":    post_data["excerpt"],
                "slug":       post_data["slug"],
                "status":     args.status,
                "author":     wp_poster.WP_DEFAULT_AUTHOR,
                "categories": [cat_id],
                "meta": {
                    "_yoast_wpseo_title":                post_data["seo_title"],
                    "_yoast_wpseo_metadesc":             post_data["meta_description"],
                    "_yoast_wpseo_focuskw":              post_data["focus_keyphrase"],
                    "_yoast_wpseo_opengraph-title":       post_data["seo_title"],
                    "_yoast_wpseo_opengraph-description": post_data["meta_description"],
                },
            }

            resp = requests.post(
                f"{api_base}/posts",
                json=payload,
                auth=wp_poster._auth(),
                headers=wp_poster._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            wp_id  = result.get("id")
            wp_url = result.get("link", "")

            db.update_post_wp(post["id"], wp_id, wp_url, status=args.status)
            db.log_entry("INFO", f"Posted draft {post['id']} to WP as {wp_id}", {"url": wp_url})
            logger.info(f"  OK — WP ID {wp_id} | {wp_url}")
            ok += 1

        except Exception as e:
            db.update_post_error(post["id"], str(e)[:500])
            db.log_entry("ERROR", f"Failed to post draft {post['id']}: {str(e)[:300]}")
            logger.error(f"  FAILED: {e}")
            fail += 1

    logger.info(f"\nDone. Posted: {ok}  Failed: {fail}")


if __name__ == "__main__":
    main()
