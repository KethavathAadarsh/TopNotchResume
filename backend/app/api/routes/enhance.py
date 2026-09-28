"""
RSEA Enhancement Routes — Resume Shine Enhancer Agent v2

GET  /api/enhance/{session_id}           → current session state (instant)
POST /api/enhance/{session_id}/analyze   → trigger 4-agent parallel analysis (async background)
POST /api/enhance/{session_id}/generate  → apply accepted improvements → new versioned DOCX
"""
import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.utils.session_store import (
    get_session, update_session, add_version, set_agent_progress,
)
from app.agents.rsea_agent import run_full_analysis, enhance_composition
from app.engine.ats_engine import compute_ats_score
from app.engine.docx_engine import render_resume

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOADS_DIR = Path(settings.downloads_dir)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ── Background analysis task ─────────────────────────────────────────────────

async def _run_analysis_background(session_id: str):
    """Runs all 4 RSEA agents, writes progress into session store as each completes."""
    session = get_session(session_id)
    if not session:
        return

    async def _progress(agent: str, status: str):
        set_agent_progress(session_id, agent, status)

    try:
        report = await run_full_analysis(
            composition=session["composition"],
            jd_analysis=session["jd_analysis"],
            missing_keywords=session.get("missing_keywords", []),
            progress_callback=_progress,
        )
        update_session(session_id, {
            "career_report": report,
            "analysis_status": "ready",
            "analysis_error": None,
        })
        logger.info("RSEA analysis complete for session %s", session_id)
    except Exception as exc:
        logger.error("RSEA analysis failed for session %s: %s", session_id, exc)
        update_session(session_id, {
            "analysis_status": "error",
            "analysis_error": str(exc),
        })


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/enhance/{session_id}")
async def get_enhance_session(session_id: str):
    """
    Returns current session state instantly.
    status: pending | analyzing | ready | error
    Frontend polls this every 2s while status == 'analyzing'.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Enhancement session not found")

    return {
        "session_id": session_id,
        "analysis_status": session["analysis_status"],
        "analysis_error": session.get("analysis_error"),
        "agent_progress": session["agent_progress"],
        "career_report": session.get("career_report"),
        "versions": session["versions"],
        "created_at": session["created_at"],
    }


@router.post("/enhance/{session_id}/analyze")
async def trigger_analysis(session_id: str):
    """
    Start the 4-agent RSEA analysis as a background task.
    Idempotent — if already analyzing or ready, returns current status.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Enhancement session not found")

    current_status = session["analysis_status"]

    if current_status == "analyzing":
        return {"status": "analyzing", "message": "Analysis already in progress"}

    if current_status == "ready":
        return {"status": "ready", "message": "Analysis already complete"}

    # Mark as analyzing and kick off background task
    update_session(session_id, {
        "analysis_status": "analyzing",
        "agent_progress": {
            "skill_gap":      "pending",
            "resume_quality": "pending",
            "learning_path":  "pending",
            "career_intel":   "pending",
        },
    })
    asyncio.create_task(_run_analysis_background(session_id))
    return {"status": "analyzing", "message": "Analysis started"}


class GenerateEnhancedRequest(BaseModel):
    accepted_improvement_ids: list[str]


@router.post("/enhance/{session_id}/generate")
async def generate_enhanced_resume(session_id: str, req: GenerateEnhancedRequest):
    """
    Apply accepted resume improvements via LLM, save new versioned DOCX.
    After saving, resets analysis_status to 'pending' so next GET re-analyzes the improved version.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Enhancement session not found")

    career_report = session.get("career_report")
    if not career_report:
        raise HTTPException(status_code=400, detail="Run analysis first before generating")

    resume_quality = career_report.get("resume_quality", {})
    all_improvements = resume_quality.get("improvements", [])
    accepted = [r for r in all_improvements if r.get("id") in req.accepted_improvement_ids]

    if not accepted:
        raise HTTPException(status_code=400, detail="No improvements selected")

    # LLM enhancement pass
    try:
        new_composition = await enhance_composition(
            composition=session["composition"],
            jd_analysis=session["jd_analysis"],
            missing_keywords=session.get("missing_keywords", []),
            accepted_improvements=accepted,
        )
    except Exception as exc:
        logger.error("Enhancement failed for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {exc}")

    # Re-score and render
    ats_result = compute_ats_score(new_composition, session["jd_analysis"])
    docx_bytes = render_resume(new_composition, resume_format=session["resume_format"])

    # Save versioned DOCX
    download_id = str(uuid.uuid4())
    candidate_name = (
        new_composition.get("personal", {}).get("name", "resume").replace(" ", "_")
    )
    next_version = len(session["versions"]) + 1
    filename = f"{candidate_name}_v{next_version}_{download_id[:8]}.docx"
    (DOWNLOADS_DIR / filename).write_bytes(docx_bytes)
    (DOWNLOADS_DIR / f"{download_id}.meta").write_text(
        f"{filename}|||{session['resume_format']}"
    )

    # Update session — add_version resets analysis_status to "pending"
    version_num = add_version(
        session_id,
        download_id=download_id,
        filename=filename,
        ats_score=ats_result["score"],
        missing_keywords=ats_result["missing_keywords"],
    )
    # Store improved composition for next enhancement cycle
    update_session(session_id, {"composition": new_composition})

    logger.info(
        "RSEA v%d generated | session=%s | ATS=%.1f",
        version_num, session_id, ats_result["score"],
    )

    return {
        "version": version_num,
        "download_id": download_id,
        "ats_score": ats_result["score"],
        "keywords_matched": ats_result["matched_keywords"],
        "keywords_missing": ats_result["missing_keywords"],
        "message": f"v{version_num} generated. Re-run analysis to see updated recommendations.",
    }
