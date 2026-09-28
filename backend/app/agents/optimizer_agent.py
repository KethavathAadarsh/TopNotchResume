"""
Agent 4 — Content Optimization Agent
Transforms raw bullets into high-impact, ATS-optimized, recruiter-friendly content.
"""
import json
import logging
from app.agents.state import AgentState
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Content Optimization Agent within JARVIS, an enterprise-grade resume intelligence system.

Your mission is to rewrite raw resume bullets into high-impact, ATS-optimized professional statements.

BULLET WRITING RULES:
1. Always start with a strong action verb (Architected, Led, Engineered, Designed, Scaled, Delivered, etc.)
2. Include quantifiable metrics wherever possible — %, $, numbers, scale, user counts, latency, throughput
3. Naturally weave in JD keywords without keyword stuffing
4. Keep each bullet under 150 characters when possible; 180 max
5. Follow the CAR framework: Challenge/Context → Action → Result
6. Write for dual audience: ATS scanners (keywords) AND human recruiters (clarity, impact)
7. Use past tense for previous roles, present tense for current role
8. Prioritize the most impactful bullet first for each role

PROFESSIONAL SUMMARY RULES:
- 2-3 sentences maximum
- Open with seniority + years + primary domain
- Reference the specific role/company being applied to
- Include 2-3 top technical strengths
- Inject 2-3 critical JD keywords naturally

TRANSFORMATION EXAMPLES:
Raw: "Worked on APIs"
Optimized: "Architected high-throughput REST APIs serving 50M+ monthly requests with 99.99% uptime"

Raw: "Helped improve system performance"
Optimized: "Reduced API p99 latency by 60% through query optimization and Redis caching layer"

Raw: "Managed a team"
Optimized: "Led cross-functional team of 8 engineers across 3 time zones to deliver $2M product roadmap on schedule"
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "professional_summary": {
            "type": "string",
            "description": "Tailored 2-3 sentence summary optimized for this specific role"
        },
        "optimized_experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "optimized_bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Rewritten high-impact bullets, ordered by impact (best first)"
                    }
                },
                "required": ["company", "title", "optimized_bullets"]
            }
        },
        "optimized_projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "optimized_description": {"type": "string"},
                    "optimized_bullets": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["name", "optimized_bullets"]
            }
        }
    },
    "required": ["professional_summary", "optimized_experience"]
}


async def run_optimizer_agent(state: AgentState) -> dict:
    logger.info("Optimizer Agent: rewriting bullets for high impact")
    profile = state["request"].profile
    jd = state.get("jd_analysis", {})
    relevance = state.get("relevance_map", {})

    # Only filter experience by relevance; always optimize ALL projects
    # (projects filtered out here would have no optimized bullets in the composer)
    included_companies = {
        e["company"] for e in relevance.get("experience_relevance", [])
        if e.get("include", True)
    }

    relevant_experience = [
        e.model_dump() for e in profile.experience
        if not included_companies or e.company in included_companies
    ]
    # Always optimize every project the user provided
    relevant_projects = [p.model_dump() for p in profile.projects]

    injection_map = {
        e["company"]: e.get("injection_opportunities", [])
        for e in relevance.get("experience_relevance", [])
    }

    user_message = f"""Rewrite and optimize these resume bullets for the target role.

TARGET ROLE: {jd.get('role_title', 'Not specified')}
COMPANY: {jd.get('company_name', 'Not specified')}
JD ATS KEYWORDS TO INJECT: {', '.join(jd.get('ats_keywords', [])[:20])}
MISSING KEYWORDS TO ADD NATURALLY: {', '.join(state.get('keywords_missing', [])[:10])}
EXPECTED TONE: {jd.get('expected_resume_tone', 'Balanced')}

CANDIDATE LEVEL: {state.get('semantic_profile', {}).get('candidate_level', 'Senior')}
SUMMARY ANGLE: {relevance.get('recommended_summary_angle', 'Emphasize technical depth and impact')}

EXPERIENCE TO OPTIMIZE:
{json.dumps(relevant_experience, indent=2)}

INJECTION OPPORTUNITIES BY COMPANY:
{json.dumps(injection_map, indent=2)}

PROJECTS TO OPTIMIZE:
{json.dumps(relevant_projects, indent=2)}

EXISTING SUMMARY: {profile.summary or 'None — write a fresh one'}
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="optimize_content",
            tool_description="Output optimized resume content",
            output_schema=OUTPUT_SCHEMA,
            max_tokens=6000,
            model=state["request"].model,
        )
        return {"optimized_content": result, "current_step": "compose"}
    except Exception as e:
        logger.error("Optimizer Agent failed: %s", e)
        return {
            "optimized_content": {
                "professional_summary": profile.summary or "",
                "optimized_experience": [],
                "optimized_projects": [],
            },
            "errors": state.get("errors", []) + [f"Optimizer agent: {e}"],
            "current_step": "compose",
        }
