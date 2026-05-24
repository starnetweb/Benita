"""
SQLite database layer for the JAMB News Blogger Agent.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
    return os.getenv("DB_PATH", str(Path(__file__).parent.parent / "db" / "blogger.db"))


def get_conn() -> sqlite3.Connection:
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'rss',
            url         TEXT,
            handle      TEXT,
            active      INTEGER NOT NULL DEFAULT 1,
            priority    INTEGER NOT NULL DEFAULT 5,
            notes       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS headlines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            title           TEXT NOT NULL,
            url             TEXT,
            summary         TEXT,
            full_content    TEXT,
            author          TEXT,
            published_at    TEXT,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
            used            INTEGER NOT NULL DEFAULT 0,
            duplicate       INTEGER NOT NULL DEFAULT 0,
            hash            TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            headline_ids    TEXT,
            wp_post_id      INTEGER,
            title           TEXT NOT NULL,
            slug            TEXT,
            meta_description TEXT,
            focus_keyphrase  TEXT,
            tags            TEXT DEFAULT '[]',
            content         TEXT,
            schema_markup   TEXT,
            status          TEXT NOT NULL DEFAULT 'draft',
            wp_url          TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            published_at    TEXT,
            word_count      INTEGER,
            error           TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            level       TEXT NOT NULL,
            message     TEXT NOT NULL,
            context     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger         TEXT NOT NULL DEFAULT 'cron',
            status          TEXT NOT NULL DEFAULT 'running',
            started_at      TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at     TEXT,
            duration_secs   INTEGER,
            headlines_found INTEGER DEFAULT 0,
            posts_published INTEGER DEFAULT 0,
            posts_errored   INTEGER DEFAULT 0,
            notes           TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_headlines_hash ON headlines(hash);
        CREATE INDEX IF NOT EXISTS idx_headlines_fetched ON headlines(fetched_at);
        CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
        CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
    """)

    # Insert default sources
    default_sources = [
        ("Google News â€” JAMB", "rss",
         "https://news.google.com/rss/search?q=JAMB+admission+2025&hl=en-NG&gl=NG&ceid=NG:en&tbs=qdr:d", None),
        ("Google News â€” UTME", "rss",
         "https://news.google.com/rss/search?q=UTME+2025+Nigeria&hl=en-NG&gl=NG&ceid=NG:en&tbs=qdr:d", None),
        ("Google News â€” SSCE Admission", "rss",
         "https://news.google.com/rss/search?q=SSCE+admission+Nigeria+2025&hl=en-NG&gl=NG&ceid=NG:en&tbs=qdr:d", None),
        ("Google News â€” Post-UTME", "rss",
         "https://news.google.com/rss/search?q=Post-UTME+screening+2025&hl=en-NG&gl=NG&ceid=NG:en&tbs=qdr:d", None),
        ("Vanguard Education", "rss",
         "https://www.vanguardngr.com/category/education/feed/", None),
        ("Punch Education", "rss",
         "https://punchng.com/category/education/feed/", None),
        ("Tribune Education", "rss",
         "https://tribuneonlineng.com/category/education/feed/", None),
        ("Twitter â€” @officialJAMB_NG", "twitter", None, "officialJAMB_NG"),
        ("Twitter â€” #JAMB2025", "twitter_hashtag", None, "JAMB2025"),
        ("Twitter â€” #PostUTME", "twitter_hashtag", None, "PostUTME"),
    ]

    for name, stype, url, handle in default_sources:
        # Deduplicate by name â€” never insert the same source name twice
        exists = cur.execute("SELECT 1 FROM sources WHERE name=?", (name,)).fetchone()
        if not exists:
            cur.execute("""
                INSERT INTO sources (name, type, url, handle)
                VALUES (?, ?, ?, ?)
            """, (name, stype, url, handle))

    # Default settings
    defaults = {
        "max_posts_per_run": "5",
        "min_word_count": "320",
        "news_lookback_hours": "48",
        "last_run": "",
        "total_posts_published": "0",
        "cron_schedule": "0 5 * * *",
        "rewriter_prompt": "",
        "claude_model": "claude-haiku-4-5",
        "wp_post_status": "draft",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()
    logger.info("Database initialised.")


# â”€â”€ Sources â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_sources(active_only=True):
    conn = get_conn()
    q = "SELECT * FROM sources"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY priority DESC, name"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_source(name, stype, url=None, handle=None, priority=5, notes=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO sources (name, type, url, handle, priority, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (name, stype, url, handle, priority, notes)
    )
    conn.commit()
    conn.close()


def update_source(source_id, **kwargs):
    allowed = {"name", "type", "url", "handle", "active", "priority", "notes"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [source_id]
    conn = get_conn()
    conn.execute(f"UPDATE sources SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_source(source_id):
    conn = get_conn()
    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit()
    conn.close()


# â”€â”€ Headlines â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def save_headline(source_id, title, url, summary, full_content, author, published_at, content_hash):
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO headlines
                (source_id, title, url, summary, full_content, author, published_at, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (source_id, title, url, summary, full_content, author, published_at, content_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate
    finally:
        conn.close()


def get_headlines(limit=50, unused_only=False, search=None):
    conn = get_conn()
    q = "SELECT h.*, s.name as source_name FROM headlines h LEFT JOIN sources s ON h.source_id=s.id"
    conds, params = [], []
    if unused_only:
        conds.append("h.used = 0")
        conds.append("h.duplicate = 0")
    if search:
        conds.append("(h.title LIKE ? OR h.summary LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY h.fetched_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_headline_used(headline_id):
    conn = get_conn()
    conn.execute("UPDATE headlines SET used=1 WHERE id=?", (headline_id,))
    conn.commit()
    conn.close()


# â”€â”€ Posts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def save_post(headline_ids, title, slug, meta_description, focus_keyphrase,
              content, schema_markup, word_count, status="draft", tags=None):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO posts
            (headline_ids, title, slug, meta_description, focus_keyphrase,
             tags, content, schema_markup, word_count, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (json.dumps(headline_ids), title, slug, meta_description, focus_keyphrase,
          json.dumps(tags or []), content, schema_markup, word_count, status))
    post_id = cur.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_post_wp(post_id, wp_post_id, wp_url, status="published"):
    conn = get_conn()
    conn.execute("""
        UPDATE posts SET wp_post_id=?, wp_url=?, status=?, published_at=datetime('now')
        WHERE id=?
    """, (wp_post_id, wp_url, status, post_id))
    conn.commit()
    conn.close()


def update_post_error(post_id, error_msg):
    conn = get_conn()
    conn.execute("UPDATE posts SET status='error', error=? WHERE id=?", (error_msg, post_id))
    conn.commit()
    conn.close()


def get_posts(limit=50, status=None):
    conn = get_conn()
    q = "SELECT * FROM posts"
    params = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# â”€â”€ Logs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def log_entry(level, message, context=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (level, message, context) VALUES (?, ?, ?)",
        (level, message, json.dumps(context) if context else None)
    )
    conn.commit()
    conn.close()


def get_logs(limit=200, level=None):
    conn = get_conn()
    q = "SELECT * FROM logs"
    params = []
    if level:
        q += " WHERE level=?"
        params.append(level)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# â”€â”€ Settings â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("""
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, str(value)))
    conn.commit()
    conn.close()


# ── Runs ──────────────────────────────────────────────────────────────────────

def start_run(trigger="cron") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO runs (trigger, status, started_at) VALUES (?, 'running', datetime('now'))",
        (trigger,)
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_run(run_id: int, status: str, headlines_found=0, posts_published=0, posts_errored=0, notes=""):
    conn = get_conn()
    conn.execute("""
        UPDATE runs SET
            status=?, finished_at=datetime('now'),
            duration_secs=CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER),
            headlines_found=?, posts_published=?, posts_errored=?, notes=?
        WHERE id=?
    """, (status, headlines_found, posts_published, posts_errored, notes, run_id))
    conn.commit()
    conn.close()


def get_runs(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    stats = {}
    stats["total_headlines"] = conn.execute("SELECT COUNT(*) FROM headlines").fetchone()[0]
    stats["unused_headlines"] = conn.execute(
        "SELECT COUNT(*) FROM headlines WHERE used=0 AND duplicate=0").fetchone()[0]
    stats["total_posts"] = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    stats["published_posts"] = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE status='published'").fetchone()[0]
    stats["error_posts"] = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE status='error'").fetchone()[0]
    stats["total_sources"] = conn.execute("SELECT COUNT(*) FROM sources WHERE active=1").fetchone()[0]
    stats["last_run"] = get_setting("last_run", "Never")
    conn.close()
    return stats
