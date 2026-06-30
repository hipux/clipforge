"""Database operations for ClipForge using aiosqlite."""
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from backend.config import DB_PATH


async def init_db():
    """Initialize database schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Videos table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                platform TEXT NOT NULL,
                title TEXT NOT NULL,
                duration REAL NOT NULL,
                thumbnail_url TEXT,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Moments table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS moments (
                id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                score REAL NOT NULL,
                reason TEXT,
                thumbnail_url TEXT,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- Score breakdown ingredients. Keep these here too so a
                -- brand-new install has them without having to run the
                -- legacy migrate_gpu_fields.py script.
                hook TEXT DEFAULT '',
                virality_score REAL DEFAULT 0,
                content_type TEXT DEFAULT '',
                hook_strength REAL DEFAULT 0,
                self_contained REAL DEFAULT 0.5,
                -- speakers stored as JSON array of person_ids; default '[]'
                -- so legacy rows still parse cleanly.
                speakers TEXT DEFAULT '[]',
                subtitle_mode TEXT DEFAULT 'ru_only',
                translated_text TEXT,
                camera_plan TEXT,
                reasoning TEXT,
                pipeline_mode TEXT DEFAULT 'gpu',
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        """)
        
        # Clips table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                moment_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                effects_json TEXT,
                status TEXT NOT NULL,
                score_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (moment_id) REFERENCES moments(id)
            )
        """)

        # Migration: add score_json to old `clips` tables that pre-date the
        # multi-dimensional virality breakdown surfacing in the UI. SQLite
        # has no IF NOT EXISTS for ADD COLUMN, so we swallow the duplicate-
        # column error — the column is already there, nothing to do.
        try:
            await db.execute("ALTER TABLE clips ADD COLUMN score_json TEXT")
        except Exception:
            pass

        # Publish log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS publish_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clip_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                youtube_url TEXT,
                method TEXT NOT NULL DEFAULT 'official',
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clip_id) REFERENCES clips(id)
            )
        """)

        # Migration: add method column to old `publish_log` tables — saves
        # distinguishing OAuth vs browser uploads when #5 ships multi-account.
        try:
            await db.execute("ALTER TABLE publish_log ADD COLUMN method TEXT NOT NULL DEFAULT 'official'")
        except Exception:
            pass

        # Migration: add account_id column to publish_log so the audit trail
        # can attribute each upload to a specific account row.
        try:
            await db.execute("ALTER TABLE publish_log ADD COLUMN account_id TEXT")
        except Exception:
            pass

        # ─── Accounts table (#5 multi-account) ────────────────────────────────
        # One row = one publishing identity = one cookie file + one preferred
        # content preset. Currently YouTube-only; the platform column is in
        # place so we can add TikTok later without further schema churn.
        #
        #   `cookies_path`     — absolute path to a Playwright/ytb-up cookie
        #                       JSON. May be empty if account is OAuth-only.
        #   `proxy`            — optional socks5:// or http://. NULL = none.
        #                       Read by youtube_browser_publisher on each
        #                       upload (proxy field is wired but unused until
        #                       #5 proxies step, which the user explicitly
        #                       deferred).
        #   `preferred_preset` — content preset id (#4) the account "thinks"
        #                       in. e.g. an anime channel picks 'films_anime'.
        #   `last_used_at`     — set when an upload is dispatched through it.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'youtube',
                cookies_path TEXT,
                proxy TEXT,
                preferred_preset TEXT NOT NULL DEFAULT 'default',
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Default account row: keeps `account_id=None` paths in #3 working.
        # We never auto-create rows from elsewhere — only via the API.
        from backend.services.content_presets import PRESETS
        default_id = "default"
        try:
            await db.execute(
                """INSERT OR IGNORE INTO accounts
                       (id, name, platform, preferred_preset)
                   VALUES (?, ?, 'youtube', ?)""",
                (default_id, "Default Channel", "default"),
            )
        except Exception:
            pass
        await db.commit()


@asynccontextmanager
async def get_db():
    """Context manager for database connections."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def save_video(video_data: Dict[str, Any]) -> None:
    """Save video metadata to database."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO videos (id, url, platform, title, duration, thumbnail_url, file_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                video_data["id"],
                video_data["url"],
                video_data["platform"],
                video_data["title"],
                video_data["duration"],
                video_data.get("thumbnail_url"),
                video_data["file_path"],
            )
        )
        await db.commit()


async def get_video(video_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve video by ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM videos WHERE id = ?", (video_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_moments(moments: List[Dict[str, Any]]) -> None:
    """Save detected moments to database."""
    async with get_db() as db:
        for moment in moments:
            await db.execute(
                """INSERT INTO moments (id, video_id, start_time, end_time, score, reason, thumbnail_url, approved)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    moment["id"],
                    moment["video_id"],
                    moment["start"],
                    moment["end"],
                    moment["score"],
                    moment["reason"],
                    moment.get("thumbnail_url"),
                    int(moment.get("approved", False)),
                )
            )
        await db.commit()


async def get_moments(video_id: str) -> List[Dict[str, Any]]:
    """Get all moments for a video."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM moments WHERE video_id = ? ORDER BY start_time",
            (video_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_moment(moment_id: str, updates: Dict[str, Any]) -> None:
    """Update moment fields."""
    async with get_db() as db:
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [moment_id]
        await db.execute(
            f"UPDATE moments SET {set_clause} WHERE id = ?",
            values
        )
        await db.commit()


async def save_clip(clip_data: Dict[str, Any]) -> None:
    """Save processed clip to database.

    `score_json` is optional — only present when the operator ran the clip
    AFTER we added the breakdown. Older clips stay NULL and the Publish UI
    treats them as "no AI score yet" rather than crashing.
    """
    async with get_db() as db:
        await db.execute(
            """INSERT INTO clips (id, moment_id, file_path, effects_json, status, score_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                clip_data["id"],
                clip_data["moment_id"],
                clip_data["file_path"],
                clip_data.get("effects_json"),
                clip_data["status"],
                clip_data.get("score_json"),
            )
        )
        await db.commit()


async def get_clips() -> List[Dict[str, Any]]:
    """Get all processed clips."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM clips ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_clip(clip_id: str) -> Optional[Dict[str, Any]]:
    """Get a single clip by ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_publish_log(log_data: Dict[str, Any]) -> None:
    """Save YouTube publish log.

    `method` records which upload path the operator used so #5 multi-account
    can correlate browser- and OAuth-uploads per-channel in audit logs.
    Defaults to 'official' for backward-compat with pre-multi-method logs.
    """
    async with get_db() as db:
        await db.execute(
            """INSERT INTO publish_log (clip_id, platform, youtube_url, method)
               VALUES (?, ?, ?, ?)""",
            (log_data["clip_id"], log_data["platform"],
             log_data.get("youtube_url"), log_data.get("method", "official"))
        )
        await db.commit()


async def get_latest_video() -> Optional[Dict[str, Any]]:
    """Get the most recently downloaded video."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM videos ORDER BY created_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_moments_by_video(video_id: str) -> List[Dict[str, Any]]:
    """Get all moments for a specific video."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM moments WHERE video_id = ? ORDER BY start_time",
            (video_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_clips_by_video(video_id: str) -> List[Dict[str, Any]]:
    """Get all clips associated with a video's moments."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT c.* FROM clips c
            JOIN moments m ON c.moment_id = m.id
            WHERE m.video_id = ?
            ORDER BY c.created_at DESC
            """,
            (video_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ─── Account CRUD (#5) ───────────────────────────────────────────────────────

async def list_accounts() -> List[Dict[str, Any]]:
    """All accounts, most-recently-used first. Default row comes first so
    the UI never accidentally hides it."""
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM accounts
               ORDER BY (id = 'default') DESC, last_used_at DESC NULLS LAST,
                        created_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_account(account: Dict[str, Any]) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO accounts
                  (id, name, platform, cookies_path, proxy, preferred_preset)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account["id"], account["name"],
             account.get("platform", "youtube"),
             account.get("cookies_path"),
             account.get("proxy"),
             account.get("preferred_preset", "default")),
        )
        await db.commit()


async def update_account(account_id: str, updates: Dict[str, Any]) -> bool:
    """Return True if any row was updated; False if account doesn't exist."""
    if not updates:
        return True
    # Whitelist updatable columns — never allow id/created_at via API.
    allowed = {"name", "platform", "cookies_path", "proxy", "preferred_preset"}
    cols = {k: v for k, v in updates.items() if k in allowed}
    if not cols:
        return False
    set_sql = ", ".join(f"{k} = ?" for k in cols.keys())
    async with get_db() as db:
        cur = await db.execute(
            f"UPDATE accounts SET {set_sql} WHERE id = ?",
            (*cols.values(), account_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_account(account_id: str) -> bool:
    if account_id == "default":
        # Default row is the system fallback for legacy code paths — never
        # delete it. Caller should send a 400 explaining why.
        return False
    async with get_db() as db:
        cur = await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()
        return cur.rowcount > 0


async def touch_account(account_id: str) -> None:
    """Mark an account as last-used now — called from the publish dispatch."""
    async with get_db() as db:
        await db.execute(
            "UPDATE accounts SET last_used_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), account_id),
        )
        await db.commit()
