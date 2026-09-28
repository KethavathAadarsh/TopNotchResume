"""
Quality Validator Agent
=======================
Compares the candidate's original 7-section profile against the generated
composition to detect missing content, truncation, and quality issues.

Returns a structured QualityReport with a score (0-100), issues list,
and actionable recommendations for the next refinement pass.
"""
import json
import logging
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the Resume Quality Validator within JARVIS, an enterprise-grade resume intelligence system.

Your job: check that ALL sections from the candidate's profile appear in the generated resume.

You receive:
1. PROFILE SUMMARY  — counts and key fields from the candidate's 7-section input
2. COMPOSITION SUMMARY — counts and content from the actual generated resume
3. PRE-DETECTED ISSUES — deterministic checks already run (trust these, incorporate them)
4. USER FEEDBACK — optional human-in-the-loop instructions

IMPORTANT RULES:
- Do NOT penalise bullet count reduction. An optimiser legitimately rewrites 6 raw bullets into
  3 polished ones — that is expected and correct behaviour, NOT an issue.
- Only flag a bullet issue if an experience entry has ZERO bullets (completely empty).
- Flag missing SECTIONS (skills entirely absent, education absent, certifications absent, etc.)
- Flag missing ROLES (a company/title in profile but not in the resume at all).

SCORING GUIDE:
  90-100 : All sections and roles present, content looks complete
  75-89  : Minor gaps — e.g. one certification missing
  55-74  : Moderate gaps — a section or role missing
  0-54   : Major gaps — multiple sections absent

Be honest. Use the full score range. If deterministic issues exist, the score MUST be below 85.
Set satisfied=true ONLY when score >= 85 AND critical_issues is empty."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "quality_score": {
            "type": "integer", "minimum": 0, "maximum": 100,
            "description": "Overall quality score 0-100"
        },
        "satisfied": {
            "type": "boolean",
            "description": "True only when score>=85 AND critical_issues is empty"
        },
        "missing_sections": {
            "type": "array", "items": {"type": "string"},
            "description": "Section names with significant missing content"
        },
        "issues": {
            "type": "array", "items": {"type": "string"},
            "description": "Specific issues found (max 8 items)"
        },
        "critical_issues": {
            "type": "array", "items": {"type": "string"},
            "description": "Must-fix issues — entire sections missing, critical data dropped"
        },
        "recommendations": {
            "type": "array", "items": {"type": "string"},
            "description": "Concrete instructions for the next generation pass (max 5 items)"
        },
    },
    "required": ["quality_score", "satisfied", "missing_sections", "issues", "critical_issues", "recommendations"],
}


def _deterministic_check(profile: dict, composition: dict) -> list[str]:
    """
    Fast deterministic presence check — runs before LLM.
    Checks for MISSING SECTIONS and MISSING ROLES only.
    Does NOT penalise bullet count reduction (the optimizer legitimately rewrites bullets).
    """
    issues = []

    # Experience — check that every profile role appears, and no role has zero bullets
    prof_exp = profile.get("experience", []) or []
    comp_exp = composition.get("experience", []) or []
    comp_companies = {e.get("company", "").lower() for e in comp_exp}
    comp_titles    = {e.get("title",   "").lower() for e in comp_exp}
    for pe in prof_exp:
        company = (pe.get("company") or "").lower()
        title   = (pe.get("title")   or "").lower()
        if company and company not in comp_companies and title not in comp_titles:
            issues.append(
                f"Experience role '{pe.get('title')} at {pe.get('company')}' is missing from resume"
            )
    # Flag any role that appears but has zero bullets
    for ce in comp_exp:
        if not ce.get("bullets"):
            issues.append(
                f"Experience '{ce.get('title')} at {ce.get('company')}' has no bullet points"
            )

    # Education — only flag if section entirely absent
    prof_edu = profile.get("education", []) or []
    comp_edu = composition.get("education", []) or []
    if prof_edu and not comp_edu:
        issues.append(
            f"Education section is missing ({len(prof_edu)} entr{'y' if len(prof_edu)==1 else 'ies'} provided)"
        )

    # Certifications — flag if section absent or fewer than provided
    prof_cert = profile.get("certifications", []) or []
    comp_cert = composition.get("certifications", []) or []
    if prof_cert and not comp_cert:
        issues.append(f"Certifications section is missing ({len(prof_cert)} provided)")
    elif len(prof_cert) > len(comp_cert):
        issues.append(
            f"Certifications: {len(prof_cert)} provided but only {len(comp_cert)} appear in resume"
        )

    # Projects — flag if section entirely absent
    prof_proj = profile.get("projects", []) or []
    comp_proj = composition.get("projects", []) or []
    if prof_proj and not comp_proj:
        issues.append(f"Projects section is missing ({len(prof_proj)} provided)")

    # Skills — flag if section absent or all categories empty
    prof_skills = profile.get("skill_categories", []) or []
    comp_skills = (
        composition.get("skill_sections")
        or composition.get("skill_categories")
        or []
    )
    valid_comp_skills = [s for s in comp_skills if isinstance(s, dict) and s.get("items")]
    if prof_skills and not valid_comp_skills:
        issues.append(f"Skills section is missing or empty ({len(prof_skills)} categories provided)")

    # Summary
    if profile.get("summary") and not composition.get("summary"):
        issues.append("Summary: provided in profile but missing from resume")

    return issues


async def run_quality_check(
    profile: dict,
    composition: dict,
    user_feedback: str = "",
    iteration: int = 1,
) -> dict:
    """
    Run a quality check comparing profile vs composition.
    Returns a QualityReport dict with score, issues, and recommendations.
    """
    det_issues = _deterministic_check(profile, composition)

    # Summarise profile for LLM (avoid sending full JSONB blobs)
    profile_summary = {
        "name": profile.get("name", ""),
        "has_summary": bool(profile.get("summary")),
        "experience": [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "bullets_count": len(e.get("bullets", [])),
            }
            for e in (profile.get("experience") or [])
        ],
        "education": [
            {"institution": e.get("institution", ""), "degree": e.get("degree", "")}
            for e in (profile.get("education") or [])
        ],
        "certifications": [
            {"name": c.get("name", ""), "issuer": c.get("issuer", "")}
            for c in (profile.get("certifications") or [])
        ],
        "projects": [{"name": p.get("name", "")} for p in (profile.get("projects") or [])],
        "skill_categories": [
            {"category": s.get("category", ""), "items_count": len(s.get("items", []))}
            for s in (profile.get("skill_categories") or [])
        ],
    }

    comp_skills = (
        composition.get("skill_sections")
        or composition.get("skill_categories")
        or []
    )
    composition_summary = {
        "has_summary": bool(composition.get("summary")),
        "experience": [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "bullets_count": len(e.get("bullets", [])),
            }
            for e in (composition.get("experience") or [])
        ],
        "education_count": len(composition.get("education") or []),
        "certifications": [
            {"name": c.get("name", "") if isinstance(c, dict) else str(c)}
            for c in (composition.get("certifications") or [])
        ],
        "projects": [
            {"name": p.get("name", "")} for p in (composition.get("projects") or [])
        ],
        "skill_sections_count": len(comp_skills),
        "section_order": composition.get("section_order", []),
    }

    user_message = f"""PROFILE (candidate's original 7-section data):
{json.dumps(profile_summary, indent=2)}

COMPOSITION (what was actually generated):
{json.dumps(composition_summary, indent=2)}

PRE-DETECTED ISSUES (deterministic checks — always incorporate these):
{json.dumps(det_issues, indent=2)}

ITERATION: {iteration}
USER FEEDBACK: {user_feedback.strip() or "(none provided)"}

Analyse the gaps and produce a quality report.
If any deterministic issues exist, quality_score must be below 85 and satisfied must be false.
If user feedback is provided, add it to your recommendations."""

    try:
        result = await call_claude_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="quality_report",
            tool_description="Output a structured resume quality report comparing profile vs composition",
            output_schema=_SCHEMA,
            max_tokens=2000,
        )
    except Exception as exc:
        logger.warning("Quality agent LLM call failed: %s — using deterministic fallback", exc)
        penalty = len(det_issues) * 15
        score = max(30, 100 - penalty)
        result = {
            "quality_score": score,
            "satisfied": score >= 85 and not det_issues,
            "missing_sections": [],
            "issues": det_issues,
            "critical_issues": det_issues[:2] if det_issues else [],
            "recommendations": (
                ["Re-run generation to ensure all sections are included"] if det_issues
                else ["Resume appears complete — no critical issues detected"]
            ),
        }

    result["iteration"] = iteration
    result["deterministic_issues"] = det_issues
    return result
