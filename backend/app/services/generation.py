"""
Post-pipeline work shared by every route that produces a resume: score, render,
store the DOCX, open an RSEA session, and persist history + artifacts.

This used to be duplicated across generate.py, stream.py, and enhance.py.
"""
import asyncio
import logging
import re
import time
import uuid
from pathlib import Path

from app.config import settings
from app.engine.ats_engine import compute_ats_score
from app.engine.docx_engine import render_resume
from app.models.schema import GenerateRequest
from app.utils.pg_store import save_generation as pg_save_generation
from app.utils.session_store import create_session

logger = logging.getLogger(__name__)

DOWNLOADS_DIR = Path(settings.downloads_dir)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename_stem(name: str) -> str:
    """
    The candidate's name ends up in a file path; strip anything that could
    traverse directories or break a Content-Disposition header.
    """
    stem = _UNSAFE_CHARS.sub("_", name or "").strip("._")
    return stem[:60] or "resume"


def is_valid_id(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False


async def store_docx(composition: dict, resume_format: str, label: str = "") -> tuple[str, str]:
    """Render and save a DOCX. Returns (download_id, filename)."""
    # python-docx is CPU-bound; rendering on the event loop stalls every other
    # request (including SSE streams) for the duration.
    docx_bytes = await asyncio.to_thread(render_resume, composition, resume_format)

    download_id = str(uuid.uuid4())
    stem = safe_filename_stem((composition.get("personal") or {}).get("name", ""))
    filename = f"{stem}{f'_{label}' if label else ''}_{download_id[:8]}.docx"

    await asyncio.to_thread((DOWNLOADS_DIR / filename).write_bytes, docx_bytes)
    # .meta stores "filename|||format" for the download endpoint
    await asyncio.to_thread(
        (DOWNLOADS_DIR / f"{download_id}.meta").write_text, f"{filename}|||{resume_format}"
    )
    return download_id, filename


def resolve_download(download_id: str) -> Path | None:
    """Map a download ID to its DOCX path, refusing anything outside DOWNLOADS_DIR."""
    if not is_valid_id(download_id):
        return None
    meta_path = DOWNLOADS_DIR / f"{download_id}.meta"
    if not meta_path.is_file():
        return None
    filename = meta_path.read_text().strip().split("|||")[0]
    file_path = (DOWNLOADS_DIR / filename).resolve()
    if file_path.parent != DOWNLOADS_DIR.resolve() or not file_path.is_file():
        return None
    return file_path


def _request_snapshot(request: GenerateRequest) -> dict:
    """What restore/refine need to rebuild the request — not the one-off knobs."""
    return request.model_dump(mode="json", exclude={"quality_feedback", "model"})


async def finalize_generation(
    request: GenerateRequest,
    state: dict,
    *,
    started_at: float,
    client_id: str | None = None,
) -> dict:
    """Turn a finished JARVIS state into a stored, downloadable resume."""
    composition = state.get("composition")
    if not composition:
        raise ValueError("Composer agent did not produce a composition. Check ANTHROPIC_API_KEY.")

    jd_analysis = state.get("jd_analysis") or {}
    resume_format = request.format.value
    ats_result = compute_ats_score(composition, jd_analysis)
    download_id, filename = await store_docx(composition, resume_format)
    elapsed_ms = int((time.monotonic() - started_at) * 1000)

    # RSEA session so the user can enhance from the download screen
    session_id = create_session(
        composition=composition,
        jd_analysis=jd_analysis,
        resume_format=resume_format,
        v1_download_id=download_id,
        v1_filename=filename,
        v1_ats_score=ats_result["score"],
        missing_keywords=ats_result["missing_keywords"],
    )

    role_title = jd_analysis.get("role_title", "")
    company = jd_analysis.get("company_name", "")
    profile = request.profile

    try:
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
            company_name=company,
            role_title=role_title,
            target_role=request.target_role or role_title,
            format=resume_format,
            max_pages=request.max_pages,
            download_id=download_id,
            session_id=session_id,
            filename=filename,
            ats_score=ats_result["score"],
            composition=composition,
            jd_analysis=jd_analysis,
            generation_ms=elapsed_ms,
            kw_matched=len(ats_result["matched_keywords"]),
            client_id=client_id,
        )
    except Exception as pg_err:
        logger.warning("PostgreSQL save failed (non-fatal): %s", pg_err)

    try:
        from app.utils.db import save_resume_history
        await save_resume_history(
            download_id=download_id,
            candidate_name=composition.get("personal", {}).get("name", ""),
            target_role=role_title,
            company=company,
            resume_format=resume_format,
            ats_score=ats_result["score"],
            keywords_matched=len(ats_result["matched_keywords"]),
            generation_time_ms=elapsed_ms,
            filename=filename,
            session_id=session_id,
            client_id=client_id,
            request=_request_snapshot(request),
            composition=composition,
            jd_analysis=jd_analysis,
        )
    except Exception as db_err:
        logger.warning("History save failed (non-fatal): %s", db_err)

    logger.info("Resume generated in %dms | ATS=%.1f | id=%s", elapsed_ms, ats_result["score"], download_id)

    return {
        "download_id": download_id,
        "session_id": session_id,
        "ats_score": ats_result["score"],
        "keywords_matched": ats_result["matched_keywords"],
        "keywords_missing": ats_result["missing_keywords"],
        "sections_included": composition.get("section_order", []),
        "generation_time_ms": elapsed_ms,
    }


def sweep_expired_downloads() -> int:
    """Delete DOCX + meta files older than the download TTL. Returns files removed."""
    cutoff = time.time() - settings.download_ttl_seconds
    removed = 0
    for path in DOWNLOADS_DIR.iterdir():
        if path.suffix not in (".docx", ".meta"):
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed
