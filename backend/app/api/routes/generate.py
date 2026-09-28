"""
Resume generation endpoint.
POST /api/generate    → sync pipeline (backward-compat)
GET  /api/download/{id} → streams the stored DOCX file
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models.schema import GenerateRequest, GenerateResponse
from app.agents.orchestrator import run_jarvis
from app.services.generation import finalize_generation, is_valid_id, resolve_download
from app.utils.guards import client_id, generation_slots, limit_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=GenerateResponse, dependencies=[Depends(limit_pipeline)])
async def generate_resume(request: GenerateRequest, owner: str | None = Depends(client_id)):
    """
    Synchronous pipeline: Profile+JD (parallel) → Relevance → Optimize → Compose → DOCX.
    Returns ATS score and a download ID.
    """
    async with generation_slots():
        started_at = time.monotonic()
        try:
            state = await run_jarvis(request)
        except Exception as exc:
            logger.exception("JARVIS pipeline failed")
            raise HTTPException(status_code=500, detail=f"Generation pipeline failed: {exc}")

        try:
            result = await finalize_generation(request, state, started_at=started_at, client_id=owner)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        except Exception as exc:
            logger.exception("Document rendering failed")
            raise HTTPException(status_code=500, detail=f"Document rendering failed: {exc}")

    return GenerateResponse(**{k: v for k, v in result.items() if k != "session_id"})


@router.get("/download/{download_id}")
async def download_resume(download_id: str):
    """Download a previously generated resume by ID."""
    if not is_valid_id(download_id):
        raise HTTPException(status_code=400, detail="Invalid download ID")

    file_path = resolve_download(download_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Resume not found or expired")

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_path.name,
    )
