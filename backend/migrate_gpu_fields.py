"""Database migration: Add GPU pipeline fields to moments table."""
import asyncio
import sys
from pathlib import Path

# Resolve DB path the same way backend/config.py does — no import needed
_PROJECT_ROOT = Path(__file__).parent.parent
_DB_PATH = _PROJECT_ROOT / "workspace" / "clipforge.db"


async def migrate():
    """Add GPU pipeline fields to moments table."""
    try:
        import aiosqlite
    except ImportError:
        print("[!] aiosqlite not installed — skipping migration")
        return

    if not _DB_PATH.exists():
        print(f"[!] Database not found at {_DB_PATH}")
        print("    It will be created automatically on first app launch.")
        return

    print(f"Connecting to {_DB_PATH}...")
    async with aiosqlite.connect(_DB_PATH) as db:
        print("Starting GPU pipeline database migration...")

        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(moments)")
        columns = await cursor.fetchall()
        existing_cols = {col[1] for col in columns}

        migrations = [
            ("hook",            "ALTER TABLE moments ADD COLUMN hook TEXT DEFAULT ''"),
            ("virality_score",  "ALTER TABLE moments ADD COLUMN virality_score REAL DEFAULT 0"),
            ("content_type",    "ALTER TABLE moments ADD COLUMN content_type TEXT DEFAULT ''"),
            ("subtitle_mode",   "ALTER TABLE moments ADD COLUMN subtitle_mode TEXT DEFAULT 'ru_only'"),
            ("translated_text", "ALTER TABLE moments ADD COLUMN translated_text TEXT"),
            ("camera_plan",     "ALTER TABLE moments ADD COLUMN camera_plan TEXT"),
            ("reasoning",       "ALTER TABLE moments ADD COLUMN reasoning TEXT"),
            ("pipeline_mode",   "ALTER TABLE moments ADD COLUMN pipeline_mode TEXT DEFAULT 'gpu'"),
            # Score-breakdown ingredients. These MUST be migrated because
            # build_score_breakdown() in score_breakdown.py reads
            # moment['hook_strength'] / moment['self_contained'] /
            # moment['speakers'] from the DB row. Without these columns
            # the score is saved into clips.score_json with mostly zeros,
            # and the Publish-page breakdown shows "no AI score".
            ("hook_strength",   "ALTER TABLE moments ADD COLUMN hook_strength REAL DEFAULT 0"),
            ("self_contained",  "ALTER TABLE moments ADD COLUMN self_contained REAL DEFAULT 0.5"),
            ("speakers",        "ALTER TABLE moments ADD COLUMN speakers TEXT DEFAULT '[]'"),
        ]



        added = 0
        for col_name, sql in migrations:
            if col_name not in existing_cols:
                print(f"  Adding column: {col_name}")
                await db.execute(sql)
                added += 1
            else:
                print(f"  Column {col_name} already exists, skipping")

        await db.commit()
        if added:
            print(f"Migration complete! Added {added} column(s).")
        else:
            print("Migration complete! All columns already exist.")


if __name__ == "__main__":
    asyncio.run(migrate())
