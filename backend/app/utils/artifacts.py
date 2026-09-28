"""
Load what a past generation produced — PostgreSQL first (when configured),
then the SQLite store. Used by restore, quality check, refine, and cover letters.
"""
from app.utils import db
from app.utils.pg_store import get_composition as pg_get_composition
from app.utils.pg_store import get_restore_data as pg_get_restore_data


async def load_restore_data(download_id: str) -> dict | None:
    """
    {profile, job_description, target_role, format, max_pages, ats_score, session_id}
    — the shape the frontend wizard pre-fills from.
    """
    data = await pg_get_restore_data(download_id)
    if data:
        return data

    artifacts = await db.get_artifacts(download_id)
    request = (artifacts or {}).get("request")
    if not request or not request.get("profile"):
        return None
    return {
        "profile": request["profile"],
        "job_description": request.get("job_description") or "",
        "target_role": request.get("target_role") or "",
        "format": request.get("format") or "ats",
        "max_pages": request.get("max_pages") or 1,
        "ats_score": artifacts["ats_score"],
        "session_id": artifacts["session_id"],
    }


async def load_composition(download_id: str) -> dict | None:
    composition = await pg_get_composition(download_id)
    if composition:
        return composition
    artifacts = await db.get_artifacts(download_id)
    composition = (artifacts or {}).get("composition")
    return composition if isinstance(composition, dict) else None


async def load_jd_analysis(download_id: str) -> dict | None:
    artifacts = await db.get_artifacts(download_id)
    jd = (artifacts or {}).get("jd_analysis")
    return jd if isinstance(jd, dict) else None
