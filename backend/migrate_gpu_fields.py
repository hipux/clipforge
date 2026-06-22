"""Database migration: Add GPU pipeline fields to moments table."""
import asyncio
import sys
import os
from pathlib import Path

# Support running directly from project root OR from within backend/
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DB_PATH


async def migrate():
    """Add GPU pipeline fields to moments table."""
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        print("Starting GPU pipeline database migration...")
        
        # Check if columns already exist
        cursor = await db.execute("PRAGMA table_info(moments)")
        columns = await cursor.fetchall()
        existing_cols = {col[1] for col in columns}
        
        # Add new columns if they don't exist
        migrations = [
            ("hook", "ALTER TABLE moments ADD COLUMN hook TEXT DEFAULT ''"),
            ("virality_score", "ALTER TABLE moments ADD COLUMN virality_score REAL DEFAULT 0"),
            ("content_type", "ALTER TABLE moments ADD COLUMN content_type TEXT DEFAULT ''"),
            ("subtitle_mode", "ALTER TABLE moments ADD COLUMN subtitle_mode TEXT DEFAULT 'ru_only'"),
            ("translated_text", "ALTER TABLE moments ADD COLUMN translated_text TEXT"),
            ("camera_plan", "ALTER TABLE moments ADD COLUMN camera_plan TEXT"),
            ("reasoning", "ALTER TABLE moments ADD COLUMN reasoning TEXT"),
            ("pipeline_mode", "ALTER TABLE moments ADD COLUMN pipeline_mode TEXT DEFAULT 'gpu'"),
        ]
        
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                print(f"  Adding column: {col_name}")
                await db.execute(sql)
            else:
                print(f"  Column {col_name} already exists, skipping")
        
        await db.commit()
        print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
