"""
Iterative Quality Refinement Routes
=====================================
POST /api/quality-check  — run quality check only (no regeneration)
POST /api/refine         — run quality check + kick off a refined pipeline job
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.agents.quality_agent import run_quality_check
from app.utils.pg_store import get_restore_data, get_composition
from app.agents.orchestrator import create_job
from app.models.schema import (
    GenerateRequest, ResumeFormat, CandidateProfile,
    ExperienceEntry, ProjectEntry, SkillCategory,
    EducationEntry, CertificationEntry,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class QualityCheckRequest(BaseModel):
    download_id: str
    user_feedback: str = ""
    iteration: int = 1


class RefineRequest(BaseModel):
    download_id: str
    user_feedback: str = ""
    iteration: int = 1
    model: Optional[str] = None  # AI model override for this refinement pass


def _build_profile(data: dict) -> CandidateProfile:
    """Reconstruct a CandidateProfile from persisted restore data dict."""
    return CandidateProfile(
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone") or None,
        location=data.get("location") or None,
        linkedin=data.get("linkedin") or None,
        github=data.get("github") or None,
        website=data.get("website") or None,
        summary=data.get("summary") or None,
        experience=[ExperienceEntry(**e) for e in (data.get("experience") or [])],
        projects=[ProjectEntry(**p) for p in (data.get("projects") or [])],
        skill_categories=[SkillCategory(**s) for s in (data.get("skill_categories") or [])],
        flat_skills=data.get("flat_skills") or [],
        education=[EducationEntry(**e) for e in (data.get("education") or [])],
        certifications=[CertificationEntry(**c) for c in (data.get("certifications") or [])],
        awards=data.get("awards") or [],
        publications=data.get("publications") or [],
    )


@router.post("/quality-check")
async def check_quality(req: QualityCheckRequest):
    """Quality check only — returns report with score, issues, recommendations."""
    restore = await get_restore_data(req.download_id)
    if not restore:
        raise HTTPException(
            status_code=404,
            detail="Resume not found in persistence store. Only resumes generated after DV2 was enabled support quality check.",
        )

    composition = await get_composition(req.download_id)
    if not composition:
        raise HTTPException(
            status_code=404,
            detail="Composition not found — this resume may have been generated before persistence was enabled.",
        )

    report = await run_quality_check(
        profile=restore["profile"],
        composition=composition,
        user_feedback=req.user_feedback,
        iteration=req.iteration,
    )
    return report


@router.post("/refine")
async def refine_resume(req: RefineRequest):
    """
    Quality check + start an iterative refinement pipeline.
    Returns {quality_report, job_id} — use job_id for SSE stream.
    """
    restore = await get_restore_data(req.download_id)
    if not restore:
        raise HTTPException(
            status_code=404,
            detail="Resume not found in persistence store. Only resumes generated after DV2 was enabled support refinement.",
        )

    composition = await get_composition(req.download_id)

    # Run quality check (non-fatal if composition missing — old generation)
    quality_report = None
    if composition:
        try:
            quality_report = await run_quality_check(
                profile=restore["profile"],
                composition=composition,
                user_feedback=req.user_feedback,
                iteration=req.iteration,
            )
        except Exception as exc:
            logger.warning("Quality check failed during refine: %s", exc)

    # Build quality feedback string to inject into the next pipeline pass
    feedback_parts: list[str] = []
    if quality_report:
        critical = quality_report.get("critical_issues") or []
        issues = quality_report.get("issues") or []
        recs = quality_report.get("recommendations") or []
        if critical:
            feedback_parts.append(
                "CRITICAL ISSUES (must fix):\n" + "\n".join(f"- {i}" for i in critical)
            )
        if issues:
            feedback_parts.append(
                "ALL ISSUES:\n" + "\n".join(f"- {i}" for i in issues)
            )
        if recs:
            feedback_parts.append(
                "RECOMMENDATIONS:\n" + "\n".join(f"- {r}" for r in recs)
            )

    if req.user_feedback.strip():
        feedback_parts.append(f"HUMAN INSTRUCTION:\n{req.user_feedback.strip()}")

    quality_feedback = "\n\n".join(feedback_parts) if feedback_parts else req.user_feedback or None

    # Reconstruct GenerateRequest from stored restore data
    try:
        profile = _build_profile(restore["profile"])
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Stored profile data could not be parsed: {exc}")

    gen_request = GenerateRequest(
        profile=profile,
        job_description=restore.get("job_description", ""),
        format=ResumeFormat(restore.get("format", "ats")),
        max_pages=int(restore.get("max_pages", 1)),
        target_role=restore.get("target_role") or None,
        quality_feedback=quality_feedback,
        model=req.model,
    )

    # Import here to avoid circular import
    from app.api.routes.stream import _run_pipeline

    job_id = str(uuid.uuid4())
    create_job(job_id)
    asyncio.create_task(_run_pipeline(job_id, gen_request))

    return {
        "quality_report": quality_report,
        "job_id": job_id,
    }
