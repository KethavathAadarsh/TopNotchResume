"""
ATS Compliance Engine
Validates resume composition for ATS compatibility and computes final scoring.
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Standard ATS-safe section names — ensures parsers can find them
STANDARD_SECTION_NAMES = {
    "experience", "work experience", "professional experience",
    "education", "skills", "technical skills",
    "projects", "certifications", "summary", "professional summary",
    "objective",
}

# Action verbs — strong bullet starters
POWER_VERBS = {
    "architected", "built", "designed", "developed", "engineered", "implemented",
    "launched", "led", "managed", "optimized", "scaled", "shipped",
    "delivered", "drove", "established", "grew", "improved", "increased",
    "reduced", "refactored", "created", "deployed", "automated", "integrated",
    "collaborated", "mentored", "partnered", "streamlined", "transformed",
}


def compute_ats_score(composition: dict, jd_analysis: dict) -> dict[str, Any]:
    """
    Compute ATS compliance score and keyword analysis.

    Returns:
        {
            "score": 0-100,
            "keyword_density": float,
            "matched_keywords": list[str],
            "missing_keywords": list[str],
            "warnings": list[str],
        }
    """
    ats_keywords = [kw.lower() for kw in jd_analysis.get("ats_keywords", [])]
    mandatory_skills = [s.lower() for s in jd_analysis.get("mandatory_skills", [])]

    # Flatten all text from the composition
    resume_text = _extract_all_text(composition).lower()

    # Keyword matching
    matched = []
    missing = []
    for kw in ats_keywords:
        normalized = kw.lower()
        if normalized in resume_text or _fuzzy_match(normalized, resume_text):
            matched.append(kw)
        else:
            missing.append(kw)

    mandatory_matched = sum(1 for s in mandatory_skills if s in resume_text)
    mandatory_total = len(mandatory_skills) or 1

    # Scoring components
    keyword_score = (len(matched) / len(ats_keywords) * 100) if ats_keywords else 80
    mandatory_score = (mandatory_matched / mandatory_total) * 100

    # ATS structure checks
    warnings = []
    structure_score = 100

    sections = [s.lower() for s in composition.get("section_order", [])]
    if "experience" not in sections:
        warnings.append("No EXPERIENCE section — ATS may penalize")
        structure_score -= 20

    if "education" not in sections:
        warnings.append("No EDUCATION section — recommended for ATS")
        structure_score -= 10

    # Check bullets start with power verbs
    weak_bullets = _count_weak_bullets(composition)
    if weak_bullets > 3:
        warnings.append(f"{weak_bullets} bullets don't start with action verbs")
        structure_score -= min(10, weak_bullets * 2)

    # Final weighted score
    final_score = (keyword_score * 0.5) + (mandatory_score * 0.3) + (structure_score * 0.2)
    final_score = max(0.0, min(100.0, final_score))

    keyword_density = len(matched) / max(len(ats_keywords), 1)

    logger.debug(
        "ATS score=%.1f | matched=%d/%d keywords | mandatory=%d/%d",
        final_score, len(matched), len(ats_keywords), mandatory_matched, mandatory_total
    )

    return {
        "score": round(final_score, 1),
        "keyword_density": round(keyword_density, 3),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "warnings": warnings,
    }


def _extract_all_text(composition: dict) -> str:
    parts = []

    summary = composition.get("summary", "")
    if summary:
        parts.append(summary)

    for exp in composition.get("experience", []):
        parts.append(exp.get("title", ""))
        parts.append(exp.get("company", ""))
        parts.extend(exp.get("bullets", []))

    for proj in composition.get("projects", []):
        parts.append(proj.get("name", ""))
        parts.extend(proj.get("bullets", []))

    for skill_section in composition.get("skill_sections", []):
        parts.extend(skill_section.get("items", []))

    for edu in composition.get("education", []):
        parts.append(edu.get("degree", ""))
        parts.append(edu.get("institution", ""))

    for cert in composition.get("certifications", []):
        parts.append(cert.get("name", ""))

    return " ".join(parts)


def _fuzzy_match(keyword: str, text: str) -> bool:
    """Handles common abbreviation/full-form pairs."""
    expansions = {
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "k8s": "kubernetes",
        "aws": "amazon web services",
        "gcp": "google cloud platform",
        "ci/cd": "continuous integration",
        "api": "application programming interface",
    }
    expanded = expansions.get(keyword)
    if expanded and expanded in text:
        return True
    # Also check reverse
    for abbr, full in expansions.items():
        if keyword == full and abbr in text:
            return True
    return False


def _count_weak_bullets(composition: dict) -> int:
    count = 0
    all_bullets = []
    for exp in composition.get("experience", []):
        all_bullets.extend(exp.get("bullets", []))
    for proj in composition.get("projects", []):
        all_bullets.extend(proj.get("bullets", []))

    for bullet in all_bullets:
        if not bullet:
            continue
        first_word = bullet.strip().split()[0].lower().rstrip(".,;:")
        if first_word not in POWER_VERBS:
            count += 1

    return count
