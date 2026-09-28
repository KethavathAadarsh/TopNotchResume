"""
Phase 3 — SSE Streaming Route
POST /api/generate/async   → starts a background pipeline job, returns {job_id}
GET  /api/generate/stream/{job_id} → Server-Sent Events: real-time pipeline steps
"""
import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schema import GenerateRequest
from app.agents.orchestrator import run_jarvis, create_job, finish_job, get_job
from app.engine.docx_engine import render_resume
from app.engine.ats_engine import compute_ats_score
from app.utils.session_store import create_session
from app.utils.pg_store import save_generation as pg_save_generation
from app.config import settings
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

DOWNLOADS_DIR = Path(settings.downloads_dir)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ── Step labels pushed to the client ────────────────────────────────────────

_STEP_LABELS = {
    "profile_agent":    {"label": "Profile Agent",    "desc": "Analyzing candidate profile — seniority, domains, achievements"},
    "jd_agent":         {"label": "JD Analyzer",      "desc": "Extracting ATS keywords, requirements, hiring signals"},
    "parallel_init":    {"label": "Intelligence Init", "desc": "Profile + JD agents running in parallel"},
    "relevance":        {"label": "Relevance Engine",  "desc": "Computing semantic alignment score, ranking experiences"},
    "optimize":         {"label": "Content Optimizer", "desc": "Rewriting bullets for high impact and ATS optimization"},
    "compose":          {"label": "Composer Agent",    "desc": "Building final layout — section order, bullet density, page fit"},
    "render":           {"label": "DOCX Engine",       "desc": "Rendering polished document with professional typography"},
    "complete":         {"label": "Complete",          "desc": "Resume is ready for download"},
}


async def _run_pipeline(job_id: str, request: GenerateRequest):
    """Background coroutine — runs JARVIS and emits SSE events."""
    job = get_job(job_id)
    if not job:
        return

    def emit(step: str, status: str, **extra):
        meta = _STEP_LABELS.get(step, {"label": step.replace("_", " ").title(), "desc": ""})
        event = {"step": step, "status": status, "label": meta["label"], "desc": meta["desc"], **extra}
        job["events"].append(event)

    try:
        emit("parallel_init", "running")
        start_ms = int(time.time() * 1000)

        # Run JARVIS pipeline
        state = await run_jarvis(request, job_id=job_id)

        emit("parallel_init", "done")
        emit("relevance", "done")
        emit("optimize", "done")
        emit("compose", "done")

        composition = state.get("composition")
        if not composition:
            raise ValueError("Composer agent did not produce a composition. Check ANTHROPIC_API_KEY.")

        emit("render", "running")
        jd_analysis = state.get("jd_analysis", {})
        ats_result = compute_ats_score(composition, jd_analysis)
        docx_bytes = render_resume(composition, resume_format=request.format.value)
        emit("render", "done")

        # Store file
        download_id = str(uuid.uuid4())
        candidate_name = composition.get("personal", {}).get("name", "resume").replace(" ", "_")
        filename = f"{candidate_name}_{download_id[:8]}.docx"
        file_path = DOWNLOADS_DIR / filename
        with open(file_path, "wb") as f:
            f.write(docx_bytes)
        meta_path = DOWNLOADS_DIR / f"{download_id}.meta"
        meta_path.write_text(f"{filename}|||{request.format.value}")

        elapsed_ms = int(time.time() * 1000) - start_ms

        # Create RSEA session so user can enhance from the download screen
        session_id = create_session(
            composition=composition,
            jd_analysis=jd_analysis,
            resume_format=request.format.value,
            v1_download_id=download_id,
            v1_filename=filename,
            v1_ats_score=ats_result["score"],
            missing_keywords=ats_result["missing_keywords"],
        )

        result = {
            "download_id": download_id,
            "session_id": session_id,
            "ats_score": ats_result["score"],
            "keywords_matched": ats_result["matched_keywords"],
            "keywords_missing": ats_result["missing_keywords"],
            "sections_included": composition.get("section_order", []),
            "generation_time_ms": elapsed_ms,
        }

        # Persist full profile to PostgreSQL DV2
        try:
            profile = request.profile
            await pg_save_generation(
                email=profile.email,
                name=profile.name,
                phone=profile.phone or "",
                location=profile.location or "",
                linkedin=profile.linkedin or "",
                github=profile.github or "",
                website=profile.website or "",
                summary=profile.summary or "",
                experience=[e.model_dump() for e in profile.experience],
                skill_categories=[c.model_dump() for c in profile.skill_categories],
                flat_skills=list(profile.flat_skills),
                projects=[p.model_dump() for p in profile.projects],
                education=[e.model_dump() for e in profile.education],
                certifications=[c.model_dump() for c in profile.certifications],
                job_description=request.job_description,
                company_name=jd_analysis.get("company_name", ""),
                role_title=jd_analysis.get("role_title", ""),
                target_role=request.target_role or jd_analysis.get("role_title", ""),
                format=request.format.value,
                max_pages=request.max_pages,
                download_id=download_id,
                session_id=session_id,
                filename=filename,
                ats_score=ats_result["score"],
                composition=composition,
                jd_analysis=jd_analysis,
                generation_ms=elapsed_ms,
                kw_matched=len(ats_result["matched_keywords"]),
            )
        except Exception as pg_err:
            logger.warning("PostgreSQL save failed: %s", pg_err)

        # Also persist to SQLite history DB
        try:
            from app.utils.db import save_resume_history
            await save_resume_history(
                download_id=download_id,
                candidate_name=composition.get("personal", {}).get("name", ""),
                target_role=state.get("jd_analysis", {}).get("role_title", ""),
                company=state.get("jd_analysis", {}).get("company_name", ""),
                resume_format=request.format.value,
                ats_score=ats_result["score"],
                keywords_matched=len(ats_result["matched_keywords"]),
                generation_time_ms=elapsed_ms,
                filename=filename,
                session_id=session_id,
            )
        except Exception as db_err:
            logger.warning("History save failed: %s", db_err)

        logger.info("Async pipeline done | job=%s | ATS=%.1f | id=%s", job_id, ats_result["score"], download_id)
        finish_job(job_id, result=result)

    except Exception as exc:
        logger.error("Async pipeline error | job=%s: %s", job_id, exc)
        finish_job(job_id, error=str(exc))


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/generate/async")
async def start_generation(request: GenerateRequest):
    """Kick off an async generation job. Returns job_id for SSE polling."""
    job_id = str(uuid.uuid4())
    create_job(job_id)
    asyncio.create_task(_run_pipeline(job_id, request))
    return {"job_id": job_id}


@router.get("/generate/result/{job_id}")
async def get_job_result(job_id: str):
    """Poll for the final result of a completed job. Used as SSE fallback."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "result": job.get("result"),
        "error": job.get("error"),
    }


@router.get("/generate/stream/{job_id}")
async def stream_generation(job_id: str):
    """Server-Sent Events stream for a running generation job."""
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        sent = 0
        elapsed_ticks = 0
        max_ticks = settings.stream_timeout_seconds * 10   # loop ticks every 0.1s
        keepalive_every = 50    # SSE comment ping every 5s
        job_finished = False
        grace_ticks = 0
        max_grace = 300         # 30s after "complete" — client should close before this

        while True:
            job = get_job(job_id)
            if not job:
                yield "data: " + json.dumps({"step": "error", "error": "Job disappeared"}) + "\n\n"
                break

            # Flush any new events first
            events = job["events"]
            while sent < len(events):
                yield "data: " + json.dumps(events[sent]) + "\n\n"
                sent += 1

            status = job["status"]
            if status in ("done", "error"):
                job_finished = True

            if job_finished:
                # Don't close from server side — let the client close after receiving
                # the "complete" event. Browser EventSource fires onerror on ANY server
                # close, even a clean one, which races with onmessage processing.
                grace_ticks += 1
                if grace_ticks >= max_grace:
                    break  # Safety exit if client never closes
                if grace_ticks % keepalive_every == 0:
                    yield ": ping\n\n"
                await asyncio.sleep(0.1)
                continue

            elapsed_ticks += 1
            if elapsed_ticks >= max_ticks:
                # The stream gave up, but the background job keeps running and will
                # still persist its result. Signal that explicitly instead of
                # emitting an "error" step, which the client treats as terminal —
                # that is what previously threw away completed generations.
                logger.warning(
                    "SSE stream for job=%s hit the %ss window; job still %s. "
                    "Client should poll /api/generate/result.",
                    job_id, settings.stream_timeout_seconds, job["status"],
                )
                yield "data: " + json.dumps({
                    "step": "stream_timeout",
                    "status": "running",
                    "message": "Still working — switching to polling.",
                }) + "\n\n"
                break

            if elapsed_ticks % keepalive_every == 0:
                yield ": ping\n\n"

            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
