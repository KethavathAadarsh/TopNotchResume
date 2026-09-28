"""
Phase 4 — Resume History Routes
GET  /api/history          → list of past generations (PostgreSQL primary, SQLite fallback)
DELETE /api/history/{id}   → soft-delete a history entry
"""
import logging
from fastapi import APIRouter, HTTPException
from app.utils.pg_store import get_history_pg, delete_history_pg
from app.utils.db import get_history as get_history_sqlite, delete_history_entry as delete_sqlite

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def list_history(limit: int = 50):
    """Return up to `limit` most recent generations, newest first.
    Reads from PostgreSQL (persisted). Falls back to SQLite if PG unavailable."""
    try:
        items = await get_history_pg(limit=min(limit, 200))
        if items:
            return {"items": items, "count": len(items)}
        # PG returned nothing — either no data yet or PG unavailable; try SQLite
        items = await get_history_sqlite(limit=min(limit, 200))
        return {"items": items, "count": len(items)}
    except Exception as exc:
        logger.error("History fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/history/{download_id}")
async def remove_history(download_id: str):
    """Soft-delete from PostgreSQL; also removes from SQLite if present."""
    if not all(c in "0123456789abcdef-" for c in download_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    await delete_history_pg(download_id)
    try:
        await delete_sqlite(download_id)
    except Exception:
        pass  # SQLite entry may not exist — non-fatal
    return {"deleted": download_id}
