"""
SQLite resume history + generation artifacts.

Besides the history row, each generation stores its request (profile + job
params), final composition, and JD analysis as JSON. That makes restore,
quality check, refine, and cover letters work without PostgreSQL — which the
free Render deployment doesn't have. PostgreSQL, when configured, stays primary.

Uses aiosqlite as a proper async context manager (connect() is entered directly,
never awaited before entering — that would double-start the background thread).
"""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = Path(settings.history_db_path)

# Columns returned by the history list — the JSON blobs stay out of it.
_LIST_COLUMNS = (
    "id, created_at, candidate, role, company, format, ats_score, "
    "kw_matched, gen_ms, filename, session_id"
)


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
        # WAL lets history reads proceed while a generation is being written.
        await db.execute("PRAGMA journal_mode=WAL")
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
        # Idempotent migrations for databases created by earlier versions
        cursor = await db.execute("PRAGMA table_info(resumes)")
        existing = {row["name"] for row in await cursor.fetchall()}
        for column in ("session_id", "client_id", "request_json", "composition_json", "jd_json"):
            if column not in existing:
                await db.execute(f"ALTER TABLE resumes ADD COLUMN {column} TEXT")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_resumes_client ON resumes(client_id, created_at)"
        )
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
    client_id: str | None = None,
    request: dict | None = None,
    composition: dict | None = None,
    jd_analysis: dict | None = None,
):
    async with _db() as db:
        await db.execute(
            """INSERT INTO resumes
               (id, created_at, candidate, role, company, format, ats_score, kw_matched,
                gen_ms, filename, session_id, client_id, request_json, composition_json, jd_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                download_id,
                datetime.now(timezone.utc).isoformat(),
                candidate_name,
                target_role,
                company,
                resume_format,
                ats_score,
                keywords_matched,
                generation_time_ms,
                filename,
                session_id,
                client_id,
                json.dumps(request) if request is not None else None,
                json.dumps(composition) if composition is not None else None,
                json.dumps(jd_analysis) if jd_analysis is not None else None,
            ),
        )
        await db.commit()


async def get_history(limit: int = 50, client_id: str | None = None) -> list[dict]:
    """History for one browser. Without a client ID there is nothing to show."""
    if not client_id:
        return []
    async with _db() as db:
        cursor = await db.execute(
            f"SELECT {_LIST_COLUMNS} FROM resumes WHERE client_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (client_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def delete_history_entry(download_id: str, client_id: str | None = None) -> bool:
    if not client_id:
        return False
    async with _db() as db:
        cursor = await db.execute(
            "DELETE FROM resumes WHERE id = ? AND client_id = ?", (download_id, client_id)
        )
        await db.commit()
        return cursor.rowcount > 0


def _loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


async def get_artifacts(download_id: str) -> dict | None:
    """Request, composition, and JD analysis stored for one generation."""
    async with _db() as db:
        cursor = await db.execute(
            "SELECT ats_score, session_id, request_json, composition_json, jd_json "
            "FROM resumes WHERE id = ?",
            (download_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "ats_score": row["ats_score"] or 0.0,
        "session_id": row["session_id"],
        "request": _loads(row["request_json"]),
        "composition": _loads(row["composition_json"]),
        "jd_analysis": _loads(row["jd_json"]),
    }
