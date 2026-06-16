"""Database operations for ClipForge using aiosqlite."""
import aiosqlite
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (moment_id) REFERENCES moments(id)
            )
        """)
        
        # Publish log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS publish_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clip_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                youtube_url TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clip_id) REFERENCES clips(id)
            )
        """)
        
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
    """Save processed clip to database."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO clips (id, moment_id, file_path, effects_json, status)
               VALUES (?, ?, ?, ?, ?)""",
            (
                clip_data["id"],
                clip_data["moment_id"],
                clip_data["file_path"],
                clip_data.get("effects_json"),
                clip_data["status"],
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
    """Save YouTube publish log."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO publish_log (clip_id, platform, youtube_url)
               VALUES (?, ?, ?)""",
            (log_data["clip_id"], log_data["platform"], log_data.get("youtube_url"))
        )
        await db.commit()
