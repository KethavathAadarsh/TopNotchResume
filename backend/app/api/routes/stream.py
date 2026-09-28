"""
Phase 3 — SSE Streaming Route
POST /api/generate/async   → starts a background pipeline job, returns {job_id}
GET  /api/generate/stream/{job_id} → Server-Sent Events: real-time pipeline steps
GET  /api/generate/result/{job_id} → poll fallback for the final result
"""
import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schema import GenerateRequest
from app.agents.orchestrator import run_jarvis, create_job, finish_job, get_job
from app.services.generation import finalize_generation
from app.utils.guards import client_id, generation_slots, limit_pipeline
from app.utils.tasks import spawn
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Step labels pushed to the client ────────────────────────────────────────

_STEP_LABELS = {
    "queued":           {"label": "Queued",            "desc": "Waiting for a free generation slot"},
    "parallel_init":    {"label": "Intelligence Init", "desc": "Profile + JD agents running in parallel"},
    "relevance":        {"label": "Relevance Engine",  "desc": "Computing semantic alignment score, ranking experiences"},
    "optimize":         {"label": "Content Optimizer", "desc": "Rewriting bullets for high impact and ATS optimization"},
    "compose":          {"label": "Composer Agent",    "desc": "Building final layout — section order, bullet density, page fit"},
    "render":           {"label": "DOCX Engine",       "desc": "Rendering polished document with professional typography"},
    "complete":         {"label": "Complete",          "desc": "Resume is ready for download"},
}


async def _run_pipeline(job_id: str, request: GenerateRequest, owner: str | None = None):
    """Background coroutine — runs JARVIS and emits SSE events."""
    job = get_job(job_id)
    if not job:
        return

    def emit(step: str, status: str, **extra):
        meta = _STEP_LABELS.get(step, {"label": step.replace("_", " ").title(), "desc": ""})
        job["events"].append({"step": step, "status": status, "label": meta["label"], "desc": meta["desc"], **extra})

    slots = generation_slots()
    try:
        if slots.locked():
            emit("queued", "running")
        async with slots:
            job["status"] = "running"
            started_at = time.monotonic()
            state = await run_jarvis(request, on_progress=emit)
            result = await finalize_generation(request, state, started_at=started_at, client_id=owner)
            emit("render", "done")
        logger.info("Async pipeline done | job=%s | ATS=%.1f", job_id, result["ats_score"])
        finish_job(job_id, result=result)

    except Exception as exc:
        logger.exception("Async pipeline error | job=%s", job_id)
        finish_job(job_id, error=str(exc) or exc.__class__.__name__)


def start_pipeline_job(request: GenerateRequest, owner: str | None) -> str:
    job_id = str(uuid.uuid4())
    create_job(job_id)
    spawn(_run_pipeline(job_id, request, owner), name=f"pipeline-{job_id[:8]}")
    return job_id


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/generate/async", dependencies=[Depends(limit_pipeline)])
async def start_generation(request: GenerateRequest, owner: str | None = Depends(client_id)):
    """Kick off an async generation job. Returns job_id for SSE polling."""
    return {"job_id": start_pipeline_job(request, owner)}


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
