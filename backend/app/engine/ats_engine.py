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
    "accelerated", "achieved", "analyzed", "authored", "championed", "coordinated",
    "cut", "defined", "directed", "enabled", "enhanced", "executed", "expanded",
    "generated", "headed", "identified", "influenced", "introduced", "maintained",
    "migrated", "modernized", "negotiated", "orchestrated", "owned", "pioneered",
    "produced", "prototyped", "rebuilt", "redesigned", "resolved", "saved",
    "secured", "spearheaded", "standardized", "supervised", "trained", "unified",
    "upgraded", "wrote",
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
    ats_keywords = _dedupe(kw for kw in jd_analysis.get("ats_keywords", []) if isinstance(kw, str))
    mandatory_skills = _dedupe(s for s in jd_analysis.get("mandatory_skills", []) if isinstance(s, str))

    # Flatten all text from the composition
    resume_text = _extract_all_text(composition).lower()

    # Keyword matching
    matched = []
    missing = []
    for kw in ats_keywords:
        if _contains_term(kw, resume_text) or _fuzzy_match(kw, resume_text):
            matched.append(kw)
        else:
            missing.append(kw)

    mandatory_matched = sum(
        1 for s in mandatory_skills if _contains_term(s, resume_text) or _fuzzy_match(s, resume_text)
    )
    mandatory_total = len(mandatory_skills) or 1

    # Scoring components
    keyword_score = (len(matched) / len(ats_keywords) * 100) if ats_keywords else 80
    mandatory_score = (mandatory_matched / mandatory_total) * 100

    # ATS structure checks
    warnings = []
    structure_score = 100

    sections = [s.lower() for s in _strings(composition.get("section_order"))]
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


def _dedupe(items) -> list[str]:
    """Lowercase, strip, and drop blanks/duplicates while keeping order."""
    seen: dict[str, None] = {}
    for item in items:
        key = item.strip().lower()
        if key:
            seen.setdefault(key, None)
    return list(seen)


def _strings(values) -> list[str]:
    return [v for v in (values or []) if isinstance(v, str)]


def _extract_all_text(composition: dict) -> str:
    parts: list[str] = []

    summary = composition.get("summary", "")
    if isinstance(summary, str):
        parts.append(summary)

    for exp in composition.get("experience") or []:
        parts.extend(_strings([exp.get("title"), exp.get("company")]))
        parts.extend(_strings(exp.get("bullets")))

    for proj in composition.get("projects") or []:
        parts.extend(_strings([proj.get("name")]))
        parts.extend(_strings(proj.get("technologies")))
        parts.extend(_strings(proj.get("bullets")))

    for skill_section in composition.get("skill_sections") or []:
        parts.extend(_strings(skill_section.get("items")))

    for edu in composition.get("education") or []:
        parts.extend(_strings([edu.get("degree"), edu.get("field"), edu.get("institution")]))

    for cert in composition.get("certifications") or []:
        parts.extend(_strings([cert.get("name")]))

    return " ".join(parts)


_TERM_CACHE: dict[str, re.Pattern] = {}


def _contains_term(term: str, text: str) -> bool:
    """
    Whole-term match. Plain substring matching produced false positives such as
    "go" in "google", "r" in anything, or "ai" in "maintain". The lookarounds
    treat letters/digits as word characters but let terms that start or end
    with symbols (c++, c#, .net, ci/cd) match correctly.
    """
    pattern = _TERM_CACHE.get(term)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")
        _TERM_CACHE[term] = pattern
    return pattern.search(text) is not None


_EXPANSIONS = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "k8s": "kubernetes",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "ci/cd": "continuous integration",
    "api": "application programming interface",
    "nlp": "natural language processing",
    "llm": "large language model",
    "js": "javascript",
    "ts": "typescript",
    "postgres": "postgresql",
}


def _fuzzy_match(keyword: str, text: str) -> bool:
    """Handles common abbreviation/full-form pairs, in both directions."""
    expanded = _EXPANSIONS.get(keyword)
    if expanded and _contains_term(expanded, text):
        return True
    for abbr, full in _EXPANSIONS.items():
        if keyword == full and _contains_term(abbr, text):
            return True
    return False


def _count_weak_bullets(composition: dict) -> int:
    count = 0
    all_bullets: list[str] = []
    for exp in composition.get("experience") or []:
        all_bullets.extend(_strings(exp.get("bullets")))
    for proj in composition.get("projects") or []:
        all_bullets.extend(_strings(proj.get("bullets")))

    for bullet in all_bullets:
        words = bullet.split()
        if not words:  # whitespace-only bullet — previously an IndexError
            continue
        first_word = words[0].lower().strip(".,;:()\"'")
        if first_word not in POWER_VERBS:
            count += 1

    return count
