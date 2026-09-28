"""
Cover Letter Generation Agent — Phase 4
Generates a targeted, personalized cover letter from the final resume
composition + JD analysis. Separate from the main JARVIS pipeline —
called on-demand after the resume is generated.
"""
import json
import logging
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert cover letter writer for a top-tier AI resume platform.

Your task is to write a compelling, personalized cover letter that:

STRUCTURE (3 paragraphs):
1. HOOK PARAGRAPH — Open with the specific role and company. Reference something specific
   about the company or role that shows genuine research. State the candidate's most relevant
   strength immediately. No generic "I am writing to apply..." openers.

2. VALUE PARAGRAPH — Bridge the candidate's TOP 2-3 achievements directly to the role's
   key requirements. Use metrics and specifics from their resume. Show, don't tell.
   Naturally weave in 2-3 JD keywords.

3. CLOSE PARAGRAPH — Express authentic enthusiasm for this specific opportunity.
   Reference the company's mission/product/growth. Confident call to action.
   Keep it brief and direct.

TONE RULES:
- Professional but human — not robotic corporate-speak
- Confident without arrogance
- Match the company stage (startup → energetic; enterprise → polished; research → thoughtful)
- Maximum 250 words total
- No "I am a hard worker" platitudes
- No "Please find attached my resume"

OUTPUT: The complete cover letter text (no subject line, no address block).
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_letter": {
            "type": "string",
            "description": "The complete cover letter text, 3 paragraphs, ~200-250 words"
        },
        "subject_line": {
            "type": "string",
            "description": "Suggested email subject line"
        },
        "tone": {
            "type": "string",
            "description": "The tone used: Professional | Energetic | Technical | Executive"
        },
    },
    "required": ["cover_letter", "subject_line", "tone"],
}


async def generate_cover_letter(
    composition: dict,
    jd_analysis: dict,
    optimized_content: dict,
) -> dict:
    """
    Generate a cover letter from the final composition + JD analysis.
    Returns {"cover_letter": str, "subject_line": str, "tone": str}
    """
    personal = composition.get("personal", {})
    summary = composition.get("summary", "")
    experience = composition.get("experience", [])
    company_stage = jd_analysis.get("company_stage", "Unknown")

    # Pull top 3 bullets from the most relevant role
    top_bullets: list[str] = []
    if experience:
        top_bullets = experience[0].get("bullets", [])[:3]

    user_message = f"""Generate a targeted cover letter for this application.

CANDIDATE:
Name: {personal.get('name', '')}
Summary: {summary}
Top role: {experience[0].get('title', '') if experience else ''} at {experience[0].get('company', '') if experience else ''}
Top achievements:
{chr(10).join(f'- {b}' for b in top_bullets)}

TARGET ROLE: {jd_analysis.get('role_title', '')} at {jd_analysis.get('company_name', '')}
COMPANY STAGE: {company_stage}
KEY REQUIREMENTS: {', '.join(jd_analysis.get('mandatory_skills', [])[:8])}
CULTURE SIGNALS: {', '.join(jd_analysis.get('culture_signals', [])[:4])}
EXPECTED TONE: {jd_analysis.get('expected_resume_tone', 'Balanced')}

FULL RESUME SUMMARY (for context):
{json.dumps({
    'experience': [{'title': e.get('title'), 'company': e.get('company'), 'bullets': e.get('bullets', [])[:2]} for e in experience[:3]],
    'skills': [cat for cat in composition.get('skill_sections', [])[:3]],
}, indent=2)}
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="generate_cover_letter",
            tool_description="Output the personalized cover letter",
            output_schema=OUTPUT_SCHEMA,
            max_tokens=2000,
        )
        logger.info("Cover letter generated: tone=%s, words≈%d",
                    result.get("tone"), len(result.get("cover_letter", "").split()))
        return result
    except Exception as exc:
        logger.error("Cover letter generation failed: %s", exc)
        raise
