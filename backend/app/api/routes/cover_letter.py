"""
Phase 4 — Cover Letter Route
POST /api/cover-letter   → generates a tailored cover letter for an existing download_id
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.cover_letter_agent import generate_cover_letter
from app.services.generation import is_valid_id
from app.utils.artifacts import load_composition, load_jd_analysis
from app.utils.guards import limit_ai

logger = logging.getLogger(__name__)
router = APIRouter()


class CoverLetterRequest(BaseModel):
    download_id: str                 # ties back to the DOCX generation
    # Optional — when omitted the server loads what it stored for download_id.
    composition: dict = {}
    jd_analysis: dict = {}
    optimized_content: dict = {}


class CoverLetterResponse(BaseModel):
    cover_letter: str
    subject_line: str
    tone: str


@router.post("/cover-letter", response_model=CoverLetterResponse, dependencies=[Depends(limit_ai)])
async def create_cover_letter(request: CoverLetterRequest):
    """Generate a personalized cover letter for a completed resume generation."""
    if not is_valid_id(request.download_id):
        raise HTTPException(status_code=400, detail="Invalid download_id")

    # The frontend sends empty objects and relies on the server to look the
    # resume up — previously nothing did, so letters were written from blanks.
    composition = request.composition or await load_composition(request.download_id)
    jd_analysis = request.jd_analysis or await load_jd_analysis(request.download_id) or {}
    if not composition:
        raise HTTPException(
            status_code=404,
            detail="Resume data not found — it may have expired or the server was redeployed. Generate the resume again.",
        )

    try:
        result = await generate_cover_letter(
            composition=composition,
            jd_analysis=jd_analysis,
            optimized_content=request.optimized_content,
        )
        return CoverLetterResponse(**result)
    except Exception as exc:
        logger.error("Cover letter endpoint failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {exc}")
