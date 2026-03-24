"""SQLite storage — deduplication, history, and digest tracking."""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

from config import db_path


_db: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = sqlite3.connect(str(db_path()), check_same_thread=False)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _init_schema(_db)
    return _db


@contextmanager
def transaction():
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def _init_schema(db: sqlite3.Connection):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS news_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE,
            title       TEXT NOT NULL,
            content     TEXT,
            source      TEXT NOT NULL,
            source_type TEXT NOT NULL,  -- x, telegram, rss, web
            category    TEXT,
            created_at  TEXT NOT NULL,
            crawled_at  TEXT NOT NULL,
            metadata    TEXT  -- JSON blob for extra fields
        );

        CREATE TABLE IF NOT EXISTS digests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            item_count  INTEGER NOT NULL,
            summary     TEXT,
            sent        INTEGER DEFAULT 0,
            sent_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS digest_items (
            digest_id   INTEGER REFERENCES digests(id),
            item_id     INTEGER REFERENCES news_items(id),
            ai_score    INTEGER,
            ai_summary  TEXT,
            PRIMARY KEY (digest_id, item_id)
        );

        CREATE INDEX IF NOT EXISTS idx_items_crawled ON news_items(crawled_at);
        CREATE INDEX IF NOT EXISTS idx_items_source ON news_items(source_type);
    """)


# --- CRUD ---

def url_exists(url: str) -> bool:
    """Check if URL already crawled (dedup)."""
    row = get_db().execute(
        "SELECT 1 FROM news_items WHERE url = ?", (url,)
    ).fetchone()
    return row is not None


def insert_item(
    url: str,
    title: str,
    content: str,
    source: str,
    source_type: str,
    category: str = "",
    created_at: str | None = None,
    metadata: dict | None = None,
) -> int | None:
    """Insert a news item. Returns row id or None if duplicate."""
    if url_exists(url):
        return None

    now = datetime.now(timezone.utc).isoformat()
    with transaction() as db:
        cur = db.execute(
            """INSERT INTO news_items
               (url, title, content, source, source_type, category, created_at, crawled_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                url,
                title,
                content or "",
                source,
                source_type,
                category or "",
                created_at or now,
                now,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def insert_items_bulk(items: list[dict]) -> tuple[int, int]:
    """Bulk insert. Returns (added, skipped)."""
    added = skipped = 0
    for item in items:
        row_id = insert_item(**item)
        if row_id:
            added += 1
        else:
            skipped += 1
    return added, skipped


def get_unsummarized_items(limit: int = 50) -> list[dict]:
    """Get items not yet included in any digest."""
    rows = get_db().execute(
        """SELECT n.* FROM news_items n
           LEFT JOIN digest_items di ON di.item_id = n.id
           WHERE di.item_id IS NULL
           ORDER BY n.crawled_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_digest(item_ids: list[int], summary: str) -> int:
    """Create a digest with associated items."""
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as db:
        cur = db.execute(
            "INSERT INTO digests (created_at, item_count, summary) VALUES (?, ?, ?)",
            (now, len(item_ids), summary),
        )
        digest_id = cur.lastrowid
        for item_id in item_ids:
            db.execute(
                "INSERT OR IGNORE INTO digest_items (digest_id, item_id) VALUES (?, ?)",
                (digest_id, item_id),
            )
        return digest_id


def mark_digest_sent(digest_id: int):
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as db:
        db.execute(
            "UPDATE digests SET sent = 1, sent_at = ? WHERE id = ?",
            (now, digest_id),
        )


def get_recent_items(hours: int = 24, source_type: str | None = None) -> list[dict]:
    """Get items crawled within the last N hours."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query = "SELECT * FROM news_items WHERE crawled_at >= ?"
    params: list = [cutoff]
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    query += " ORDER BY crawled_at DESC"
    rows = get_db().execute(query, params).fetchall()
    return [dict(r) for r in rows]
