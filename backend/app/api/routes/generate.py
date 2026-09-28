"""
Resume generation endpoint.
POST /api/generate    → sync pipeline (backward-compat)
GET  /api/download/{id} → streams the stored DOCX file
"""
import uuid
import time
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schema import GenerateRequest, GenerateResponse
from app.agents.orchestrator import run_jarvis
from app.engine.docx_engine import render_resume
from app.engine.ats_engine import compute_ats_score
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOADS_DIR = Path(settings.downloads_dir)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/generate", response_model=GenerateResponse)
async def generate_resume(request: GenerateRequest):
    """
    Synchronous pipeline: Profile+JD (parallel) → Relevance → Optimize → Compose → DOCX.
    Returns ATS score and a download ID valid for 1 hour.
    """
    start_ms = int(time.time() * 1000)

    try:
        state = await run_jarvis(request)
    except Exception as exc:
        logger.error("JARVIS pipeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Generation pipeline failed: {exc}")

    composition = state.get("composition")
    if not composition:
        raise HTTPException(
            status_code=500,
            detail="Composer agent did not produce a composition. Check ANTHROPIC_API_KEY.",
        )

    jd_analysis = state.get("jd_analysis", {})
    ats_result = compute_ats_score(composition, jd_analysis)

    try:
        docx_bytes = render_resume(composition, resume_format=request.format.value)
    except Exception as exc:
        logger.error("DOCX rendering failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Document rendering failed: {exc}")

    download_id = str(uuid.uuid4())
    candidate_name = composition.get("personal", {}).get("name", "resume").replace(" ", "_")
    filename = f"{candidate_name}_{download_id[:8]}.docx"
    file_path = DOWNLOADS_DIR / filename

    with open(file_path, "wb") as f:
        f.write(docx_bytes)

    # .meta stores "filename|||format" for the download endpoint
    meta_path = DOWNLOADS_DIR / f"{download_id}.meta"
    meta_path.write_text(f"{filename}|||{request.format.value}")

    # Persist to history
    try:
        from app.utils.db import save_resume_history
        elapsed_ms = int(time.time() * 1000) - start_ms
        await save_resume_history(
            download_id=download_id,
            candidate_name=composition.get("personal", {}).get("name", ""),
            target_role=jd_analysis.get("role_title", ""),
            company=jd_analysis.get("company_name", ""),
            resume_format=request.format.value,
            ats_score=ats_result["score"],
            keywords_matched=len(ats_result["matched_keywords"]),
            generation_time_ms=elapsed_ms,
            filename=filename,
        )
    except Exception as db_err:
        logger.warning("History save failed (non-fatal): %s", db_err)
        elapsed_ms = int(time.time() * 1000) - start_ms

    logger.info("Resume generated in %dms | ATS=%.1f | id=%s", elapsed_ms, ats_result["score"], download_id)

    return GenerateResponse(
        download_id=download_id,
        ats_score=ats_result["score"],
        keywords_matched=ats_result["matched_keywords"],
        keywords_missing=ats_result["missing_keywords"],
        sections_included=composition.get("section_order", []),
        generation_time_ms=elapsed_ms,
    )


@router.get("/download/{download_id}")
async def download_resume(download_id: str):
    """Download a previously generated resume by ID."""
    if not all(c in "0123456789abcdef-" for c in download_id):
        raise HTTPException(status_code=400, detail="Invalid download ID")

    meta_path = DOWNLOADS_DIR / f"{download_id}.meta"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found or expired")

    # Meta format: "filename|||format" (format part optional for backwards compat)
    meta_content = meta_path.read_text().strip()
    filename = meta_content.split("|||")[0]
    file_path = DOWNLOADS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found")

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
