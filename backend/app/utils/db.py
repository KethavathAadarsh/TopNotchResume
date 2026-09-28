"""
Phase 4 — SQLite Resume History
Uses aiosqlite as a proper async context manager (connect() is entered directly,
never awaited before entering — that would double-start the background thread).
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

import aiosqlite

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/history.db")


@asynccontextmanager
async def _db():
    """Yield an open aiosqlite connection with Row factory set."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_db():
    """Create tables if they don't exist. Called at startup."""
    async with _db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL,
                candidate   TEXT NOT NULL,
                role        TEXT,
                company     TEXT,
                format      TEXT,
                ats_score   REAL,
                kw_matched  INTEGER,
                gen_ms      INTEGER,
                filename    TEXT,
                session_id  TEXT
            )
        """)
        # Migration: add session_id to existing databases
        try:
            await db.execute("ALTER TABLE resumes ADD COLUMN session_id TEXT")
        except Exception:
            pass  # column already exists
        await db.commit()
    logger.info("DB initialised at %s", _DB_PATH)


async def save_resume_history(
    download_id: str,
    candidate_name: str,
    target_role: str,
    company: str,
    resume_format: str,
    ats_score: float,
    keywords_matched: int,
    generation_time_ms: int,
    filename: str,
    session_id: str | None = None,
):
    async with _db() as db:
        await db.execute(
            """INSERT INTO resumes
               (id, created_at, candidate, role, company, format, ats_score, kw_matched, gen_ms, filename, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                download_id,
                datetime.utcnow().isoformat(),
                candidate_name,
                target_role,
                company,
                resume_format,
                ats_score,
                keywords_matched,
                generation_time_ms,
                filename,
                session_id,
            ),
        )
        await db.commit()


async def get_history(limit: int = 50) -> list[dict]:
    async with _db() as db:
        cursor = await db.execute(
            "SELECT * FROM resumes ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def delete_history_entry(download_id: str):
    async with _db() as db:
        await db.execute("DELETE FROM resumes WHERE id = ?", (download_id,))
        await db.commit()
