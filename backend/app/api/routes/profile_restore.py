"""
Profile Restore Route
GET /api/history/{download_id}/restore
Returns the full candidate profile + job params saved at generation time.
Used by the frontend wizard to pre-fill all 7 sections from a history entry.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.utils.pg_store import get_restore_data

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/history/{download_id}/restore")
async def restore_profile(download_id: str):
    """
    Retrieve saved profile and generation parameters for a past resume.
    Returns 404 if not found or PostgreSQL not configured.
    """
    data = await get_restore_data(download_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Restore data not found. This resume may have been generated before persistent storage was enabled.",
        )
    return data
