"""
JAMB News Blogger Agent â€” Main Orchestrator
Runs daily at 6am Lagos time (WAT, UTC+1).
Usage: python agent.py [--test] [--dry-run]
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows so Unicode chars don't crash the console/log
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pytz
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

# â”€â”€ Logging setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
LOG_PATH = os.getenv("LOG_PATH", str(BASE_DIR / "logs" / "agent.log"))
Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("agent")

# â”€â”€ Local imports (after logging) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
sys.path.insert(0, str(Path(__file__).parent))
import db
import scraper
import rewriter
import wp_poster


MAX_POSTS = int(os.getenv("MAX_POSTS_PER_RUN", "5"))
LAGOS_TZ = pytz.timezone("Africa/Lagos")


def run(dry_run: bool = False, test_mode: bool = False, trigger: str = "cron"):
    db.init_db()

    # Read runtime settings from DB (allow admin overrides)
    max_posts = int(db.get_setting("max_posts_per_run", str(MAX_POSTS)))

    now_lagos = datetime.now(LAGOS_TZ).strftime("%Y-%m-%d %H:%M WAT")
    logger.info(f"{'='*60}")
    logger.info(f"Agent run started: {now_lagos}")
    logger.info(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'} | {'TEST' if test_mode else 'NORMAL'}")
    logger.info(f"{'='*60}")

    run_id = db.start_run(trigger=trigger)
    db.log_entry("INFO", f"Agent run started at {now_lagos}")
    db.set_setting("last_run", datetime.utcnow().isoformat())

    # â”€â”€ Step 1: Test WordPress connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not dry_run:
        logger.info("Testing WordPress connection...")
        if not wp_poster.test_wp_connection():
            logger.error("Cannot reach WordPress. Aborting.")
            db.log_entry(“ERROR”, “WordPress connection failed - run aborted”)
            db.finish_run(run_id, “failed”, notes=”WordPress connection failed”)
            return

    # ── Step 2: Scrape sources â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    sources = db.get_sources(active_only=True)
    logger.info(f"Active sources: {len(sources)}")

    if test_mode:
        sources = sources[:3]

    all_articles = scraper.scrape_all_sources(sources)
    logger.info(f"Articles scraped: {len(all_articles)}")

    if not all_articles:
        logger.warning("No new articles found. Run complete.")
        db.log_entry("WARNING", "No articles found this run")
        db.finish_run(run_id, "completed", headlines_found=0, notes="No articles found")
        return

    # â”€â”€ Step 3: Save headlines, deduplicate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    new_articles = []
    for art in all_articles:
        saved = db.save_headline(
            source_id=art.get("source_id"),
            title=art["title"],
            url=art.get("url", ""),
            summary=art.get("summary", ""),
            full_content=art.get("full_content", ""),
            author=art.get("author", ""),
            published_at=art.get("published_at", ""),
            content_hash=art["hash"],
        )
        if saved:
            new_articles.append(art)
        else:
            logger.debug(f"Duplicate skipped: {art['title'][:60]}")

    logger.info(f"New (non-duplicate) articles: {len(new_articles)}")
    db.log_entry("INFO", f"Scraped {len(all_articles)} articles, {len(new_articles)} new")

    if not new_articles:
        logger.info(“All articles were duplicates. Nothing to post.”)
        db.finish_run(run_id, “completed”, headlines_found=len(all_articles), notes=”All duplicates”)
        return

    # ── Step 4: Group by topic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    groups = rewriter.group_articles_by_topic(new_articles)
    logger.info(f"Topic groups: {len(groups)}")

    # Limit posts per run
    groups = groups[:max_posts]

    posts_published = 0
    posts_errored = 0

    # â”€â”€ Step 5: For each group â€” rewrite â†’ save â†’ post â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for i, group in enumerate(groups, 1):
        titles = [a["title"][:60] for a in group]
        logger.info(f"Processing group {i}/{len(groups)}: {titles}")

        headline_ids = []
        for art in group:
            rows = db.get_headlines(limit=1, search=art["title"][:50])
            if rows:
                headline_ids.append(rows[0]["id"])

        try:
            # Rewrite with Claude
            post_data = rewriter.rewrite_articles(group)

            # Validate SEO
            issues = rewriter.validate_post(post_data)
            if issues:
                logger.warning(f"SEO issues in group {i}: {issues}")
                db.log_entry("WARNING", f"SEO issues in post {i}", {"issues": issues})

            word_count = rewriter.count_words(post_data.get("content_html", ""))
            post_data["word_count"] = word_count

            # Save post draft to DB
            post_id = db.save_post(
                headline_ids=headline_ids,
                title=post_data.get("seo_title", ""),
                slug=post_data.get("slug", ""),
                meta_description=post_data.get("meta_description", ""),
                focus_keyphrase=post_data.get("focus_keyphrase", ""),
                tags=post_data.get("tags", []),
                content=post_data.get("content_html", ""),
                schema_markup=str(post_data.get("schema_markup", "")),
                word_count=word_count,
                status="draft",
            )
            logger.info(f"Saved draft post ID {post_id}: '{post_data.get('seo_title', '')[:60]}'")

            if dry_run:
                logger.info(f"[DRY-RUN] Would publish: {post_data.get('seo_title', '')}")
                continue

            # Post to WordPress
            wp_result = wp_poster.post_to_wordpress(post_data)
            db.update_post_wp(post_id, wp_result["wp_post_id"], wp_result["wp_url"])

            # Mark headlines as used
            for hid in headline_ids:
                db.mark_headline_used(hid)

            posts_published += 1
            db.log_entry("INFO", f"Published post ID {post_id} to WP as {wp_result['wp_post_id']}", wp_result)

        except Exception as e:
            posts_errored += 1
            logger.error(f"Group {i} failed: {e}", exc_info=True)
            db.log_entry("ERROR", f"Group {i} failed: {str(e)[:500]}")
            if "post_id" in dir():
                db.update_post_error(post_id, str(e)[:500])

    # â”€â”€ Step 6: Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    total_published = int(db.get_setting("total_posts_published", "0")) + posts_published
    db.set_setting("total_posts_published", total_published)

    summary = (f"Run complete. Published: {posts_published}, "
               f"Errors: {posts_errored}, Total ever: {total_published}")
    logger.info(summary)
    db.log_entry("INFO", summary)

    run_status = "failed" if posts_errored and not posts_published else "completed"
    db.finish_run(run_id, run_status,
                  headlines_found=len(all_articles),
                  posts_published=posts_published,
                  posts_errored=posts_errored,
                  notes=summary)


def main():
    parser = argparse.ArgumentParser(description="JAMB News Blogger Agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrape and rewrite but do NOT post to WordPress")
    parser.add_argument("--test", action="store_true",
                        help="Use only first 3 sources (faster for testing)")
    parser.add_argument("--trigger", default="cron",
                        help="Run trigger: cron or manual")
    args = parser.parse_args()
    run(dry_run=args.dry_run, test_mode=args.test, trigger=args.trigger)


if __name__ == "__main__":
    main()
