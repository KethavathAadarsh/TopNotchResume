"""
Agent 3 — Matching & Relevance Engine
Phase 2: Enriched with semantic pre-scoring via OpenAI embeddings before
handing off to GPT for final relevance decisions. Embedding scores ground
the LLM in actual vector similarity, not just keyword overlap.
"""
import json
import logging
from app.agents.state import AgentState
from app.utils.claude_client import call_claude_structured
from app.utils.semantic import compute_profile_jd_similarity, semantic_skill_coverage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Matching & Relevance Engine within JARVIS, an enterprise-grade resume intelligence system.

You receive a semantic candidate profile AND a structured JD analysis.
Your mission is to act as the intelligence brain of the resume system:

SCORING:
- Compute an overall alignment score (0-100) between the candidate and this role
- Score each experience entry (0-100) for relevance to this specific JD
- Score each project (0-100) for relevance
- Identify which skill categories are most aligned

KEYWORD STRATEGY:
- Map which candidate skills directly match JD mandatory/preferred skills
- Identify critical ATS keywords MISSING from the candidate's current profile
- Recommend natural keyword injection points (which bullets can be edited to include missing keywords)

PRIORITIZATION:
- Rank which 2-4 roles should appear prominently in the resume
- Determine if any old roles should be compressed or omitted for 1-page fit
- Identify which 2-3 projects (if any) to include

OUTPUT:
A precise relevance map that drives the optimizer and composer agents."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_match_score": {
            "type": "number",
            "description": "0-100 semantic alignment score"
        },
        "experience_relevance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "relevance_score": {"type": "number"},
                    "include": {"type": "boolean"},
                    "priority_rank": {"type": "integer"},
                    "compress": {"type": "boolean", "description": "Reduce bullet count for page fit"},
                    "matched_keywords": {"type": "array", "items": {"type": "string"}},
                    "injection_opportunities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to naturally weave into bullets for this role"
                    }
                },
                "required": ["company", "title", "relevance_score", "include", "priority_rank"]
            }
        },
        "project_relevance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "relevance_score": {"type": "number"},
                    "include": {"type": "boolean"},
                    "matched_keywords": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name", "relevance_score", "include"]
            }
        },
        "keywords_matched": {
            "type": "array",
            "items": {"type": "string"},
            "description": "JD ATS keywords already present in the candidate profile"
        },
        "keywords_missing": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Critical JD keywords absent from candidate profile"
        },
        "skills_to_highlight": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills to emphasize prominently given this JD"
        },
        "recommended_summary_angle": {
            "type": "string",
            "description": "How to angle the professional summary for this specific role"
        }
    },
    "required": [
        "overall_match_score", "experience_relevance", "project_relevance",
        "keywords_matched", "keywords_missing", "skills_to_highlight"
    ]
}


async def run_relevance_agent(state: AgentState) -> dict:
    logger.info("Relevance Agent: computing alignment")
    profile = state["request"].profile
    semantic = state.get("semantic_profile", {})
    jd = state.get("jd_analysis", {})
    jd_text = state["request"].job_description

    # Phase 2: Pre-compute semantic scores with embeddings before calling GPT
    profile_blob = (
        f"{profile.name} "
        + " ".join(e.title + " " + e.company + " " + " ".join(e.bullets) for e in profile.experience)
        + " ".join(s for cat in profile.skill_categories for s in cat.items)
        + " ".join(profile.flat_skills)
    )
    candidate_skills = list(profile.flat_skills) + [
        s for cat in profile.skill_categories for s in cat.items
    ]
    jd_skills = jd.get("mandatory_skills", []) + jd.get("preferred_skills", [])

    semantic_score, skill_coverage = await __import__("asyncio").gather(
        compute_profile_jd_similarity(profile_blob, jd_text),
        semantic_skill_coverage(candidate_skills, jd_skills),
    )
    logger.info(
        "Relevance Agent: semantic pre-score=%.1f, skill coverage=%.0f%%",
        semantic_score, skill_coverage["coverage"] * 100,
    )

    user_message = f"""Compute relevance alignment between this candidate and job.

SEMANTIC PRE-SCORE (embedding cosine similarity): {semantic_score}/100
SEMANTIC SKILL COVERAGE: {round(skill_coverage['coverage'] * 100)}% of JD skills matched
SEMANTICALLY MISSING SKILLS: {', '.join(skill_coverage['missing'][:15])}

SEMANTIC PROFILE:
{json.dumps(semantic, indent=2)}

JD ANALYSIS:
{json.dumps(jd, indent=2)}

CANDIDATE EXPERIENCE (raw):
{json.dumps([e.model_dump() for e in profile.experience], indent=2)}

CANDIDATE PROJECTS (raw):
{json.dumps([p.model_dump() for p in profile.projects], indent=2)}

TARGET FORMAT: {state['request'].format.value}
MAX PAGES: {state['request'].max_pages}

Use the semantic pre-score and skill coverage as a calibration signal.
Your overall_match_score should align with the embedding similarity unless
you have strong reasons to adjust (e.g. the candidate has exact title match,
or the JD is unusually verbose skewing the embedding).
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="compute_relevance",
            tool_description="Output the relevance map",
            output_schema=OUTPUT_SCHEMA,
            model=state["request"].model,
        )
        return {
            "relevance_map": result,
            "keywords_matched": result.get("keywords_matched", []),
            "keywords_missing": result.get("keywords_missing", []),
            "ats_score": result.get("overall_match_score", 0.0),
            "current_step": "optimize",
        }
    except Exception as e:
        logger.error("Relevance Agent failed: %s", e)
        return {
            "relevance_map": {},
            "keywords_matched": [],
            "keywords_missing": [],
            "ats_score": 0.0,
            "errors": state.get("errors", []) + [f"Relevance agent: {e}"],
            "current_step": "optimize",
        }
