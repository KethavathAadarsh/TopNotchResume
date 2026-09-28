"""
Phase 4 — Resume History Routes
GET  /api/history          → this browser's past generations (PostgreSQL primary, SQLite fallback)
DELETE /api/history/{id}   → delete one of this browser's history entries

Scoped by the anonymous X-Client-Id header so one visitor can't list another
visitor's names, roles, and companies.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.services.generation import is_valid_id
from app.utils.guards import client_id
from app.utils.pg_store import get_history_pg, delete_history_pg
from app.utils.db import get_history as get_history_sqlite, delete_history_entry as delete_sqlite

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history")
async def list_history(limit: int = 50, owner: str | None = Depends(client_id)):
    """Return up to `limit` of this browser's most recent generations, newest first."""
    limit = max(1, min(limit, 200))
    try:
        items = await get_history_pg(limit=limit, client_id=owner)
        if not items:
            # PG returned nothing — either no data yet or PG unavailable; try SQLite
            items = await get_history_sqlite(limit=limit, client_id=owner)
        return {"items": items, "count": len(items)}
    except Exception as exc:
        logger.error("History fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail="History fetch failed")


@router.delete("/history/{download_id}")
async def remove_history(download_id: str, owner: str | None = Depends(client_id)):
    """Soft-delete from PostgreSQL; also removes from SQLite if present."""
    if not is_valid_id(download_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    if not owner:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id header")
    await delete_history_pg(download_id, client_id=owner)
    try:
        await delete_sqlite(download_id, client_id=owner)
    except Exception as exc:
        logger.warning("SQLite history delete failed (non-fatal): %s", exc)
    return {"deleted": download_id}
