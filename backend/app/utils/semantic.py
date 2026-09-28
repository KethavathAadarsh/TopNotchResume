"""
Semantic Intelligence Layer — Phase 2

Deep semantic matching between candidate profiles and job descriptions.

Anthropic has no embeddings API, so this layer runs on one of two backends:

  * "embedding" — OpenAI text-embedding-3-small, used when OPENAI_API_KEY is set.
    This is the higher-quality path and matches the original behaviour.
  * "lexical"   — a dependency-free token/trigram cosine fallback used when no
    embedding key is configured. It catches wording overlap and near-spellings
    ("Postgres"/"PostgreSQL") but NOT conceptual synonyms ("K8s"/"Kubernetes").

Score calibration differs per backend, because lexical cosines sit in a lower,
narrower band than embedding cosines. Both paths return the same 0-100 scale.
Vectors are cached in-process by content hash.
"""
import asyncio
import hashlib
import logging
import re
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# In-process vector cache (md5(text) → vector)
_cache: dict[str, Any] = {}

# Per-backend calibration: (floor, ceiling) cosine mapped onto 0-100, plus the
# default skill-match threshold.
_CALIBRATION = {
    "embedding": {"profile": (0.30, 1.00), "experience": (0.20, 1.00), "skill_threshold": 0.72},
    "lexical":   {"profile": (0.08, 0.85), "experience": (0.05, 0.75), "skill_threshold": 0.60},
}

_STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or that the to with
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def active_backend() -> str:
    """Which similarity backend is in use. Exposed for /health."""
    return "embedding" if settings.openai_api_key else "lexical"


# ── Lexical backend ──────────────────────────────────────────────────────────

def _lexical_vector(text: str, trigram_weight: float) -> dict[str, float]:
    """
    Sparse bag of word tokens (plus optional character trigrams), L2-normalised.

    `trigram_weight` is the crux of the two modes:
      * 0.0 for long documents — trigrams add noise and cost at blob length.
      * 1.0 for short terms like skill names, where the single word token would
        otherwise swamp the trigram signal and "Postgres"/"PostgreSQL" would not
        match. At parity, that pair scores ~0.76 while "Java"/"JavaScript" stays
        at ~0.39, which is the separation the match threshold relies on.
    """
    lowered = text.lower()
    tokens = [t for t in _TOKEN_RE.findall(lowered) if t not in _STOPWORDS and len(t) > 1]

    counts: dict[str, float] = {}
    for tok in tokens:
        counts[f"w:{tok}"] = counts.get(f"w:{tok}", 0.0) + 1.0
        if trigram_weight > 0 and len(tok) > 3:
            for i in range(len(tok) - 2):
                key = f"g:{tok[i:i + 3]}"
                counts[key] = counts.get(key, 0.0) + trigram_weight

    norm = sum(v * v for v in counts.values()) ** 0.5
    if norm == 0:
        return {}
    return {k: v / norm for k, v in counts.items()}


def _sparse_cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
    return float(sum(v * larger.get(k, 0.0) for k, v in smaller.items()))


# ── Embedding backend ────────────────────────────────────────────────────────

async def _openai_embedding(text: str) -> list[float]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text[:8000],
    )
    return response.data[0].embedding


def _dense_cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


# ── Backend-agnostic surface ─────────────────────────────────────────────────

async def _get_vector(text: str, mode: str = "doc") -> Any:
    """
    Fetch or return a cached vector for a single text string.

    `mode` is "doc" (long text) or "term" (short strings like skill names); it
    only affects the lexical backend's trigram weighting, but is part of the
    cache key so the two representations never collide.
    """
    backend = active_backend()
    key = f"{backend}:{mode}:{hashlib.md5(text.encode()).hexdigest()}"
    if key in _cache:
        return _cache[key]

    trigram_weight = 1.0 if mode == "term" else 0.0

    if backend == "lexical":
        vec = _lexical_vector(text, trigram_weight)
    else:
        try:
            vec = await _openai_embedding(text)
        except Exception as exc:
            # Fall back rather than returning a zero vector, which would silently
            # score everything as a non-match.
            logger.warning("Embedding API failed (len=%d): %s — using lexical", len(text), exc)
            vec = _lexical_vector(text, trigram_weight)

    _cache[key] = vec
    return vec


def _cosine(a: Any, b: Any) -> float:
    if isinstance(a, dict) or isinstance(b, dict):
        # A degraded embedding call can leave one side lexical; only compare
        # like with like.
        if not (isinstance(a, dict) and isinstance(b, dict)):
            return 0.0
        return _sparse_cosine(a, b)
    return _dense_cosine(a, b)


def _scale(sim: float, kind: str) -> float:
    floor, ceiling = _CALIBRATION[active_backend()][kind]
    if ceiling <= floor:
        return 0.0
    return round(max(0.0, min(100.0, (sim - floor) / (ceiling - floor) * 100)), 1)


# ── Public API ───────────────────────────────────────────────────────────────

async def compute_profile_jd_similarity(profile_text: str, jd_text: str) -> float:
    """
    Semantic similarity between candidate profile blob and job description blob.
    Returns a 0-100 score, calibrated per backend.
    """
    profile_vec, jd_vec = await asyncio.gather(
        _get_vector(profile_text[:6000]),
        _get_vector(jd_text[:4000]),
    )
    return _scale(_cosine(profile_vec, jd_vec), "profile")


async def semantic_skill_coverage(
    candidate_skills: list[str],
    jd_skills: list[str],
    threshold: float | None = None,
) -> dict[str, Any]:
    """
    For each JD-required skill, find the closest candidate skill by cosine.
    Returns matched pairs, missing skills, and a 0-1 coverage ratio.
    """
    if not candidate_skills or not jd_skills:
        return {"matched": [], "missing": list(jd_skills), "coverage": 0.0}

    if threshold is None:
        threshold = _CALIBRATION[active_backend()]["skill_threshold"]

    all_texts = list(set(candidate_skills) | set(jd_skills))
    vectors = await asyncio.gather(*[_get_vector(t, mode="term") for t in all_texts])
    vec_map: dict[str, Any] = dict(zip(all_texts, vectors))

    matched: list[dict] = []
    missing: list[str] = []

    for jd_skill in jd_skills:
        jd_vec = vec_map.get(jd_skill)
        best_sim, best_cand = 0.0, ""
        for cand_skill in candidate_skills:
            sim = _cosine(jd_vec, vec_map.get(cand_skill))
            if sim > best_sim:
                best_sim, best_cand = sim, cand_skill
        if best_sim >= threshold:
            matched.append({"jd": jd_skill, "candidate": best_cand, "score": round(best_sim, 3)})
        else:
            missing.append(jd_skill)

    coverage = len(matched) / len(jd_skills)
    logger.debug(
        "Semantic skill coverage [%s]: %d/%d (%.0f%%)",
        active_backend(), len(matched), len(jd_skills), coverage * 100,
    )
    return {"matched": matched, "missing": missing, "coverage": round(coverage, 3)}


async def rank_experiences_semantically(
    experiences: list[dict],
    jd_text: str,
) -> list[dict]:
    """
    Re-rank experience entries by semantic similarity to the JD.
    Each entry gets a `semantic_score` 0-100 injected.
    """
    if not experiences:
        return experiences

    jd_vec = await _get_vector(jd_text[:4000])

    async def _score_exp(exp: dict) -> tuple[dict, float]:
        exp_blob = f"{exp.get('title', '')} {exp.get('company', '')} {' '.join(exp.get('bullets', []))}"
        exp_vec = await _get_vector(exp_blob[:2000])
        return exp, _scale(_cosine(exp_vec, jd_vec), "experience")

    results = await asyncio.gather(*[_score_exp(e) for e in experiences])
    return [{**exp, "semantic_score": score} for exp, score in results]
