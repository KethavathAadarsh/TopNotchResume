"""
MR. JARVIS — Master Orchestrator v2
Phase 2: Profile Agent + JD Agent run in parallel, cutting pipeline time ~30%.
Remaining agents (Relevance → Optimizer → Composer) execute sequentially.
"""
import asyncio
import logging
import time
from collections.abc import Callable
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.profile_agent import run_profile_agent
from app.agents.jd_agent import run_jd_agent
from app.agents.relevance_agent import run_relevance_agent
from app.agents.optimizer_agent import run_optimizer_agent
from app.agents.composer_agent import run_composer_agent
from app.models.schema import GenerateRequest

logger = logging.getLogger(__name__)

# In-memory job store for SSE streaming
# job_id → {"status", "events": [...], "result": None, "error": None}
_active_jobs: dict[str, dict] = {}


async def run_parallel_init(state: AgentState) -> dict:
    """Phase 2: Profile Agent + JD Agent run simultaneously via asyncio.gather."""
    logger.info("JARVIS: parallel init — Profile + JD agents running simultaneously")
    profile_result, jd_result = await asyncio.gather(
        run_profile_agent(state),
        run_jd_agent(state),
    )
    merged: dict = {**profile_result, **jd_result}
    merged["current_step"] = "relevance"
    merged["errors"] = profile_result.get("errors", []) + jd_result.get("errors", [])
    return merged


def _build_jarvis():
    workflow = StateGraph(AgentState)
    workflow.add_node("parallel_init", run_parallel_init)
    workflow.add_node("compute_relevance", run_relevance_agent)
    workflow.add_node("optimize_content", run_optimizer_agent)
    workflow.add_node("compose_resume", run_composer_agent)
    workflow.set_entry_point("parallel_init")
    workflow.add_edge("parallel_init", "compute_relevance")
    workflow.add_edge("compute_relevance", "optimize_content")
    workflow.add_edge("optimize_content", "compose_resume")
    workflow.add_edge("compose_resume", END)
    return workflow.compile()


jarvis = _build_jarvis()


# Graph node → the step key the frontend progress list uses, and the step that
# starts once it finishes.
_NODE_STEPS = {
    "parallel_init":     ("parallel_init", "relevance"),
    "compute_relevance": ("relevance", "optimize"),
    "optimize_content":  ("optimize", "compose"),
    "compose_resume":    ("compose", "render"),
}


async def run_jarvis(
    request: GenerateRequest,
    on_progress: Callable[[str, str], None] | None = None,
) -> AgentState:
    """
    Execute the full JARVIS pipeline.

    Streams node updates from LangGraph so `on_progress(step, status)` fires as
    each agent actually finishes — previously every step was reported "done"
    only after the whole pipeline returned, so the UI sat on step 1 for minutes.
    """

    def _emit(step: str, status: str):
        if on_progress:
            on_progress(step, status)

    initial_state: AgentState = {
        "request": request,
        "semantic_profile": None,
        "jd_analysis": None,
        "relevance_map": None,
        "optimized_content": None,
        "composition": None,
        "ats_score": 0.0,
        "keywords_matched": [],
        "keywords_missing": [],
        "errors": [],
        "current_step": "start",
    }

    logger.info("JARVIS: starting pipeline for '%s'", request.profile.name)
    _emit("parallel_init", "running")

    # Nodes return partial updates with no reducers, so replaying them in
    # order over the initial state reproduces what ainvoke() would return.
    final_state: dict = dict(initial_state)
    async for chunk in jarvis.astream(initial_state, stream_mode="updates"):
        for node, update in chunk.items():
            if update:
                final_state.update(update)
            done_step, next_step = _NODE_STEPS.get(node, (node, None))
            _emit(done_step, "done")
            if next_step:
                _emit(next_step, "running")

    if final_state.get("errors"):
        logger.warning("JARVIS completed with errors: %s", final_state["errors"])
    else:
        logger.info(
            "JARVIS: pipeline complete. ATS score=%.1f, keywords matched=%d",
            final_state.get("ats_score", 0),
            len(final_state.get("keywords_matched", [])),
        )

    return final_state


# ── Job management helpers for SSE ──────────────────────────────────────────

def get_job(job_id: str) -> dict | None:
    return _active_jobs.get(job_id)


def create_job(job_id: str):
    _active_jobs[job_id] = {
        "status": "pending", "events": [], "result": None, "error": None,
        "created_at": time.monotonic(),
    }


def prune_jobs(max_age_seconds: float) -> int:
    """
    Drop old jobs so the in-memory store doesn't grow forever. Finished jobs go
    after max_age; a job still "running" at twice that is treated as stuck.
    """
    now = time.monotonic()
    stale = [
        job_id for job_id, job in _active_jobs.items()
        if (age := now - job.get("created_at", now)) > max_age_seconds
        and (job["status"] in ("done", "error") or age > 2 * max_age_seconds)
    ]
    for job_id in stale:
        del _active_jobs[job_id]
    return len(stale)


def finish_job(job_id: str, result: dict | None = None, error: str | None = None):
    if job_id in _active_jobs:
        _active_jobs[job_id]["result"] = result
        _active_jobs[job_id]["error"] = error
        # Append event BEFORE setting status — SSE generator checks status to decide
        # when to flush, so the complete event must be in the list first.
        _active_jobs[job_id]["events"].append({
            "step": "complete" if result else "error",
            "status": "done" if result else "error",
            **({"result": result} if result else {"error": error}),
        })
        _active_jobs[job_id]["status"] = "done" if result else "error"
