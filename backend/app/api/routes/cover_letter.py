"""
Phase 4 — Cover Letter Route
POST /api/cover-letter   → generates a tailored cover letter for an existing download_id
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.cover_letter_agent import generate_cover_letter
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOADS_DIR = Path(settings.downloads_dir)


class CoverLetterRequest(BaseModel):
    download_id: str           # ties back to the DOCX generation
    composition: dict          # the full composition JSON
    jd_analysis: dict          # the JD analysis from the pipeline
    optimized_content: dict    # optimizer agent output


class CoverLetterResponse(BaseModel):
    cover_letter: str
    subject_line: str
    tone: str


@router.post("/cover-letter", response_model=CoverLetterResponse)
async def create_cover_letter(request: CoverLetterRequest):
    """Generate a personalized cover letter for a completed resume generation."""
    if not all(c in "0123456789abcdef-" for c in request.download_id):
        raise HTTPException(status_code=400, detail="Invalid download_id")

    try:
        result = await generate_cover_letter(
            composition=request.composition,
            jd_analysis=request.jd_analysis,
            optimized_content=request.optimized_content,
        )
        return CoverLetterResponse(**result)
    except Exception as exc:
        logger.error("Cover letter endpoint failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {exc}")
