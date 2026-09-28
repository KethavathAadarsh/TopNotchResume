"""
Agent 1 — Profile Understanding Agent
Converts raw candidate profile into a semantic profile graph used by downstream agents.
"""
import json
import logging
from app.agents.state import AgentState
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Profile Understanding Agent within JARVIS, an enterprise-grade resume intelligence system.

Your mission is to deeply analyze a candidate's raw profile data and extract semantic meaning:
- Determine seniority level (Junior / Mid / Senior / Staff / Principal / Executive)
- Identify primary technical domains and depth of expertise in each
- Surface leadership indicators (team size managed, cross-functional work, mentorship)
- Extract all quantifiable achievements (%, $, numbers, scale, impact)
- Identify core competencies vs. peripheral skills
- Assess career trajectory (upward / lateral / specialist deepening)
- Flag the strongest differentiators that set this candidate apart

Output a structured semantic profile that downstream agents will use to intelligently match against job requirements."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_level": {
            "type": "string",
            "description": "Inferred seniority: Junior | Mid | Senior | Staff | Principal | Director | VP | CTO"
        },
        "years_of_experience": {"type": "number"},
        "primary_domains": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3-5 technical/domain areas of expertise"
        },
        "technical_depth": {
            "type": "object",
            "description": "Map of skill/domain to depth score 1-10",
            "additionalProperties": {"type": "number"}
        },
        "leadership_indicators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Evidence of leadership, management, or influence"
        },
        "quantified_achievements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "All measurable impacts found in the profile"
        },
        "top_differentiators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What makes this candidate stand out"
        },
        "career_trajectory": {
            "type": "string",
            "description": "Upward progression | Specialist deepening | Lateral breadth | Career pivot"
        },
        "all_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Comprehensive flat list of all skills mentioned"
        },
        "experience_summary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "key_achievements": {"type": "array", "items": {"type": "string"}},
                    "relevance_keywords": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    "required": [
        "candidate_level", "years_of_experience", "primary_domains",
        "technical_depth", "top_differentiators", "all_skills",
        "career_trajectory", "experience_summary"
    ]
}


async def run_profile_agent(state: AgentState) -> dict:
    logger.info("Profile Agent: analyzing candidate profile")
    profile = state["request"].profile

    user_message = f"""Analyze this candidate profile:

NAME: {profile.name}
EMAIL: {profile.email}
LOCATION: {profile.location or 'Not provided'}

EXPERIENCE:
{json.dumps([e.model_dump() for e in profile.experience], indent=2)}

PROJECTS:
{json.dumps([p.model_dump() for p in profile.projects], indent=2)}

SKILLS:
{json.dumps([c.model_dump() for c in profile.skill_categories], indent=2)}
Flat skills: {', '.join(profile.flat_skills)}

EDUCATION:
{json.dumps([e.model_dump() for e in profile.education], indent=2)}

CERTIFICATIONS:
{json.dumps([c.model_dump() for c in profile.certifications], indent=2)}

EXISTING SUMMARY: {profile.summary or 'None provided'}
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="analyze_profile",
            tool_description="Output the structured semantic profile analysis",
            output_schema=OUTPUT_SCHEMA,
            model=state["request"].model,
        )
        return {"semantic_profile": result, "current_step": "jd_analysis"}
    except Exception as e:
        logger.error("Profile Agent failed: %s", e)
        return {
            "semantic_profile": {"candidate_level": "Senior", "primary_domains": [], "all_skills": []},
            "errors": state.get("errors", []) + [f"Profile agent: {e}"],
            "current_step": "jd_analysis",
        }
