"""
Agent 2 — Job Description Analyzer
Extracts structured requirements, ATS keywords, and hiring signals from the JD.
"""
import logging
from app.agents.state import AgentState
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Job Description Analysis Agent within JARVIS, an enterprise-grade resume intelligence system.

Your mission is to deeply parse a job description and extract:

REQUIREMENTS EXTRACTION:
- Hard skills: mandatory vs. preferred technical skills
- Soft skills and behavioral expectations
- ATS keywords: exact phrases a recruiter/ATS would scan for (include common abbreviations and full forms)
- Seniority signals: language that reveals the expected experience level
- Domain expertise required

HIDDEN SIGNAL EXTRACTION:
- Company maturity stage (startup / growth / enterprise / public)
- Engineering culture signals (move fast / process-oriented / research-focused)
- Expected resume tone (quantitative / narrative / technical / executive)
- Technical density expected (heavy jargon / balanced / high-level)
- Interview process hints (system design / coding / behavioral / case-based)

OUTPUT:
Produce a precise, structured JD analysis that enables the relevance engine to match candidates optimally."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "role_title": {"type": "string"},
        "company_name": {"type": "string"},
        "seniority_level": {"type": "string"},
        "mandatory_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills explicitly required (must-have)"
        },
        "preferred_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills mentioned as nice-to-have or preferred"
        },
        "ats_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exact phrases/keywords an ATS would scan for — include both acronyms and full forms"
        },
        "soft_skills": {
            "type": "array",
            "items": {"type": "string"}
        },
        "domain_focus": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Primary technical/business domains this role operates in"
        },
        "company_stage": {
            "type": "string",
            "description": "Startup | Growth | Enterprise | Public Company | Government"
        },
        "culture_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Inferred culture/environment signals"
        },
        "expected_resume_tone": {
            "type": "string",
            "description": "Quantitative | Executive | Technical | Narrative | Balanced"
        },
        "key_responsibilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 5-7 core responsibilities extracted from the JD"
        },
        "years_experience_required": {"type": "number"},
        "education_requirements": {"type": "string"}
    },
    "required": [
        "role_title", "mandatory_skills", "preferred_skills", "ats_keywords",
        "domain_focus", "expected_resume_tone", "key_responsibilities"
    ]
}


async def run_jd_agent(state: AgentState) -> dict:
    logger.info("JD Agent: analyzing job description")
    jd_text = state["request"].job_description
    target_role = state["request"].target_role or ""

    user_message = f"""Analyze this job description:

TARGET ROLE (user-specified): {target_role or 'Not specified'}

JOB DESCRIPTION:
{jd_text}
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="analyze_jd",
            tool_description="Output the structured JD analysis",
            output_schema=OUTPUT_SCHEMA,
            model=state["request"].model,
        )
        return {"jd_analysis": result, "current_step": "relevance"}
    except Exception as e:
        logger.error("JD Agent failed: %s", e)
        return {
            "jd_analysis": {"role_title": target_role, "mandatory_skills": [], "ats_keywords": []},
            "errors": state.get("errors", []) + [f"JD agent: {e}"],
            "current_step": "relevance",
        }
