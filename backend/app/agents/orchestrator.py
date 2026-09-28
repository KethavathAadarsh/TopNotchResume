"""
MR. JARVIS — Master Orchestrator v2
Phase 2: Profile Agent + JD Agent run in parallel, cutting pipeline time ~30%.
Remaining agents (Relevance → Optimizer → Composer) execute sequentially.
"""
import asyncio
import logging
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


async def run_jarvis(request: GenerateRequest, job_id: str | None = None) -> AgentState:
    """Execute the full JARVIS pipeline. If job_id is given, emits progress events for SSE."""

    def _emit(step: str, status: str, **extra):
        if job_id and job_id in _active_jobs:
            _active_jobs[job_id]["events"].append({"step": step, "status": status, **extra})

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
    _emit("pipeline", "started")

    final_state = await jarvis.ainvoke(initial_state)

    if final_state.get("errors"):
        logger.warning("JARVIS completed with errors: %s", final_state["errors"])
    else:
        logger.info(
            "JARVIS: pipeline complete. ATS score=%.1f, keywords matched=%d",
            final_state.get("ats_score", 0),
            len(final_state.get("keywords_matched", [])),
        )

    _emit("pipeline", "complete")
    return final_state


# ── Job management helpers for SSE ──────────────────────────────────────────

def get_job(job_id: str) -> dict | None:
    return _active_jobs.get(job_id)


def create_job(job_id: str):
    _active_jobs[job_id] = {"status": "pending", "events": [], "result": None, "error": None}


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
