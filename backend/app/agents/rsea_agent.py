"""
RSEA v2 — Resume Shine Enhancer Agent (Multi-Agent Career Intelligence System)

Four specialist sub-agents run in parallel via asyncio.gather:
  1. Skill Gap Analyst     — deep technical + soft skill gap analysis + readiness score
  2. Learning Path Advisor — personalized roadmap: resources, timelines, certifications, projects
  3. Resume Quality Agent  — bullet depth, ATS coverage, quantification, impact language
  4. Career Intel Agent    — interview prep, culture signals, negotiation leverage, insider tips

Called by enhance.py as a background asyncio.Task. Results stored in session["career_report"].
"""
import asyncio
import json
import logging
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — Skill Gap Analyst
# ═══════════════════════════════════════════════════════════════════════════════

_SKILL_GAP_SYSTEM = """You are a senior technical recruiter and engineering career coach with 15 years hiring experience at FAANG, top startups, and quant firms.

Your job: perform an honest, deep skill gap analysis between a candidate's resume and a target job description.

Rules:
- Only flag skills that are EXPLICITLY in the JD or strongly implied by role context
- Severity: critical = mandatory + completely absent; high = mandatory + partially present; medium = preferred + absent; low = nice-to-have
- Acknowledge candidate's adjacent skills that partially cover a gap
- Strengths should be genuine differentiators, not just "has Python"
- Readiness score: 0-100, be calibrated (most candidates score 45-75, not 90+)"""

_SKILL_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_readiness_score": {"type": "integer", "description": "0-100. Calibrated fit for this specific role right now."},
        "readiness_label": {"type": "string", "description": "e.g. 'Strong match', 'Qualified with gaps', 'Stretch role', 'Significant upskilling needed'"},
        "readiness_summary": {"type": "string", "description": "3-4 sentence honest assessment. What makes this candidate competitive? What's holding them back?"},
        "skill_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                    "category": {"type": "string", "description": "Languages / Infrastructure / ML-AI / Data / Leadership / Domain / Cloud / Security / etc."},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "jd_context": {"type": "string", "description": "Why this skill matters for this specific role"},
                    "candidate_adjacent": {"type": "string", "description": "Related skills the candidate has that partially cover this gap. Empty string if none."},
                    "is_mandatory": {"type": "boolean"}
                },
                "required": ["skill", "category", "severity", "jd_context", "candidate_adjacent", "is_mandatory"]
            }
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Genuine competitive strengths of this specific candidate for this specific role"
        },
        "competitive_advantages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Rare or unusual angles that differentiate this candidate from the typical applicant pool"
        },
        "critical_blockers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills or experiences that are absolute dealbreakers if missing — must fix before applying"
        }
    },
    "required": ["overall_readiness_score", "readiness_label", "readiness_summary", "skill_gaps", "strengths", "competitive_advantages", "critical_blockers"]
}


async def _run_skill_gap_agent(composition: dict, jd_analysis: dict, missing_keywords: list[str]) -> dict:
    candidate_text = json.dumps({
        "summary": composition.get("summary", ""),
        "experience": [
            {"title": e.get("title"), "company": e.get("company"), "bullets": e.get("bullets", [])}
            for e in composition.get("experience", [])
        ],
        "skills": composition.get("skill_sections", []),
        "projects": [
            {"name": p.get("name"), "technologies": p.get("technologies", []), "bullets": p.get("bullets", [])}
            for p in composition.get("projects", [])
        ],
        "certifications": composition.get("certifications", []),
    }, indent=2)

    user_msg = f"""JOB REQUIREMENTS:
Role: {jd_analysis.get('role_title', 'Unknown')} at {jd_analysis.get('company_name', 'Unknown')}
Seniority: {jd_analysis.get('seniority_level', 'Unknown')}
Mandatory skills: {', '.join(jd_analysis.get('mandatory_skills', []))}
Preferred skills: {', '.join(jd_analysis.get('preferred_skills', [])[:15])}
ATS keywords missing from resume: {', '.join(missing_keywords[:20])}

CANDIDATE PROFILE (from resume):
{candidate_text}

Perform a deep skill gap analysis. Be honest — this helps the candidate know exactly what to work on."""

    return await call_claude_structured(
        system_prompt=_SKILL_GAP_SYSTEM,
        user_message=user_msg,
        tool_name="skill_gap_analysis",
        tool_description="Deep skill gap analysis between candidate and JD",
        output_schema=_SKILL_GAP_SCHEMA,
        max_tokens=3000,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — Learning Path Advisor
# ═══════════════════════════════════════════════════════════════════════════════

_LEARNING_SYSTEM = """You are an expert career development coach and curriculum designer. You've helped hundreds of engineers land roles at top companies.

Your job: create a personalized, actionable learning roadmap to close specific skill gaps for a target role.

Rules:
- Recommend REAL, well-known resources (actual course names, books, certification programs)
- Give realistic time estimates — most people learn a new technology in 2-8 weeks with focused effort
- Project ideas should be portfolio-ready and directly relevant to the target role
- Order by impact: fix critical gaps first
- Quick wins: things achievable in 1-2 weeks that immediately strengthen the application"""

_LEARNING_SCHEMA = {
    "type": "object",
    "properties": {
        "total_prep_timeline": {"type": "string", "description": "Realistic timeline to close all critical+high gaps (e.g. '3-4 months full-time, 6-8 months part-time')"},
        "executive_summary": {"type": "string", "description": "1-2 sentences: if you follow this roadmap, what will you be able to do?"},
        "quick_wins": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Specific action to take this week"},
                    "time_required": {"type": "string", "description": "e.g. '2 hours', '1 day'"},
                    "impact": {"type": "string"}
                },
                "required": ["action", "time_required", "impact"]
            }
        },
        "learning_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "estimated_weeks": {"type": "integer", "description": "Weeks to reach working proficiency"},
                    "resources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Specific course/book/resource name"},
                                "type": {"type": "string", "description": "course / book / docs / platform / youtube"},
                                "why": {"type": "string", "description": "Why this resource over others"}
                            },
                            "required": ["name", "type", "why"]
                        }
                    },
                    "project_idea": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string", "description": "What to build and what it demonstrates"},
                            "tech_stack": {"type": "array", "items": {"type": "string"}},
                            "github_ready": {"type": "boolean", "description": "Should this be on GitHub?"}
                        },
                        "required": ["title", "description", "tech_stack", "github_ready"]
                    },
                    "why_matters": {"type": "string", "description": "Why this skill is critical for the target role"}
                },
                "required": ["skill", "priority", "estimated_weeks", "resources", "project_idea", "why_matters"]
            }
        },
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full certification name"},
                    "provider": {"type": "string"},
                    "relevance": {"type": "string", "description": "How directly this cert addresses the JD"},
                    "estimated_months": {"type": "integer"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "exam_cost_usd": {"type": "integer", "description": "Approximate exam cost"},
                    "prep_resource": {"type": "string", "description": "Best prep course/material"}
                },
                "required": ["name", "provider", "relevance", "estimated_months", "priority"]
            }
        },
        "github_portfolio_tips": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific GitHub/portfolio improvements to make this week (pinned repos, README quality, contribution graph, etc.)"
        }
    },
    "required": ["total_prep_timeline", "executive_summary", "quick_wins", "learning_items", "certifications"]
}


async def _run_learning_path_agent(skill_gaps: list[dict], jd_analysis: dict) -> dict:
    critical_gaps = [g for g in skill_gaps if g.get("severity") in ("critical", "high")]

    user_msg = f"""TARGET ROLE: {jd_analysis.get('role_title', '')} at {jd_analysis.get('company_name', '')}
Seniority: {jd_analysis.get('seniority_level', '')}
Company stage: {jd_analysis.get('company_stage', '')}

SKILL GAPS TO ADDRESS (ordered by severity):
{json.dumps(skill_gaps, indent=2)}

Create a personalized, time-bound learning roadmap to close these gaps.
Focus most detail on critical and high severity gaps ({len(critical_gaps)} found).
For medium/low gaps, brief recommendations are fine."""

    return await call_claude_structured(
        system_prompt=_LEARNING_SYSTEM,
        user_message=user_msg,
        tool_name="learning_roadmap",
        tool_description="Personalized learning roadmap to close skill gaps",
        output_schema=_LEARNING_SCHEMA,
        max_tokens=4000,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 3 — Resume Quality Agent
# ═══════════════════════════════════════════════════════════════════════════════

_RESUME_QUALITY_SYSTEM = """You are a world-class resume writer and ATS optimization expert. You've reviewed 10,000+ resumes for top tech companies.

Analyze this resume composition and provide specific, actionable improvements:
1. ATS keyword coverage vs the JD
2. Bullet point strength: action verbs, quantification, XYZ format (accomplished X by doing Y, resulting in Z)
3. Summary effectiveness
4. Impact language and leadership signals
5. Section completeness and ordering

For each improvement, be SPECIFIC — show concrete before/after examples where possible."""

_RESUME_QUALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique ID like rec_keywords, rec_bullets_1, etc."},
                    "type": {"type": "string", "description": "missing_keywords | bullet_depth | quantify_results | leadership_signals | summary_optimization | section_reorder | achievement_framing"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "impact": {"type": "string"},
                    "example_fix": {"type": "string", "description": "Concrete example: 'Change: X → Better: Y'"},
                    "keywords_to_add": {"type": "array", "items": {"type": "string"}, "description": "Keywords to weave in (for keyword improvements)"}
                },
                "required": ["id", "type", "priority", "title", "description", "impact", "example_fix"]
            }
        },
        "scores": {
            "type": "object",
            "properties": {
                "bullet_quality": {"type": "integer", "description": "0-100: strength of bullet points"},
                "ats_coverage": {"type": "integer", "description": "0-100: keyword coverage"},
                "summary_effectiveness": {"type": "integer", "description": "0-100: summary quality"},
                "quantification_rate": {"type": "integer", "description": "0-100: % of bullets with metrics"},
                "leadership_language": {"type": "integer", "description": "0-100: presence of leadership signals"}
            },
            "required": ["bullet_quality", "ats_coverage", "summary_effectiveness", "quantification_rate", "leadership_language"]
        },
        "top_missing_keywords": {"type": "array", "items": {"type": "string"}},
        "strongest_bullets": {"type": "array", "items": {"type": "string"}, "description": "Top 3 strongest existing bullets (positive reinforcement)"},
        "weakest_bullets": {"type": "array", "items": {"type": "string"}, "description": "Top 3 weakest bullets to prioritize improving"}
    },
    "required": ["improvements", "scores", "top_missing_keywords"]
}


async def _run_resume_quality_agent(composition: dict, jd_analysis: dict, missing_keywords: list[str]) -> dict:
    all_bullets = [
        b for exp in composition.get("experience", []) for b in exp.get("bullets", [])
    ] + [
        b for proj in composition.get("projects", []) for b in proj.get("bullets", [])
    ]

    user_msg = f"""JOB: {jd_analysis.get('role_title', '')} at {jd_analysis.get('company_name', '')}
Mandatory skills: {', '.join(jd_analysis.get('mandatory_skills', []))}
ATS keywords missing: {', '.join(missing_keywords[:20])}
Expected tone: {jd_analysis.get('expected_resume_tone', 'Technical')}

RESUME COMPOSITION:
Summary: {composition.get('summary', '(none)')}

Experience bullets ({len(all_bullets)} total):
{json.dumps(all_bullets[:25], indent=2)}

Skills sections: {json.dumps(composition.get('skill_sections', []), indent=2)}

Projects: {json.dumps([{'name': p.get('name'), 'technologies': p.get('technologies', []), 'bullets': p.get('bullets', [])} for p in composition.get('projects', [])], indent=2)}

Provide specific, actionable resume improvements. Include example fixes."""

    return await call_claude_structured(
        system_prompt=_RESUME_QUALITY_SYSTEM,
        user_message=user_msg,
        tool_name="resume_quality_analysis",
        tool_description="Detailed resume quality analysis with actionable improvements",
        output_schema=_RESUME_QUALITY_SCHEMA,
        max_tokens=3000,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 4 — Career Intel Agent
# ═══════════════════════════════════════════════════════════════════════════════

_CAREER_INTEL_SYSTEM = """You are a senior career intelligence analyst with deep expertise in tech hiring, company cultures, and interview processes.

Your job: extract hidden signals from a job description to give the candidate strategic preparation intel.

Be specific and tactical:
- What will interviewers actually probe for (based on JD language)?
- What does the JD reveal about team culture, pain points, and work style?
- What leverage does this candidate have for negotiation?
- What red flags or challenges should they be aware of?

Focus on actionable insights, not generic advice."""

_CAREER_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "interview_prep": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "why": {"type": "string", "description": "Why this topic will likely come up (based on specific JD language)"},
                    "depth": {"type": "string", "enum": ["surface", "moderate", "deep"]},
                    "prep_resources": {"type": "array", "items": {"type": "string"}, "description": "Specific books/courses/repos to prepare"},
                    "likely_questions": {"type": "array", "items": {"type": "string"}, "description": "2-3 actual questions the interviewer might ask"},
                    "candidate_angle": {"type": "string", "description": "How THIS candidate should frame their answer given their background"}
                },
                "required": ["topic", "why", "depth", "prep_resources", "likely_questions", "candidate_angle"]
            }
        },
        "culture_signals": {"type": "string", "description": "What the JD reveals about team culture, working style, and expectations"},
        "company_stage_intel": {"type": "string", "description": "Company maturity signals and what that means for the role (scope, autonomy, politics, growth)"},
        "role_realities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Real challenges and realities of this role based on JD signals — things not explicitly stated"
        },
        "negotiation_leverage": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "how_to_use": {"type": "string"}
                },
                "required": ["point", "how_to_use"]
            }
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Potential concerns in the JD worth probing during interviews"
        },
        "application_strategy": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Strategic tips specific to THIS application (referral approach, portfolio, cover letter angle, etc.)"
        },
        "questions_to_ask": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Smart questions for the candidate to ask in interviews that demonstrate deep understanding"
        }
    },
    "required": ["interview_prep", "culture_signals", "company_stage_intel", "role_realities", "negotiation_leverage", "red_flags", "application_strategy", "questions_to_ask"]
}


async def _run_career_intel_agent(composition: dict, jd_analysis: dict, skill_gaps: list[dict]) -> dict:
    strengths_summary = ", ".join([
        e.get("title", "") + " @ " + e.get("company", "")
        for e in composition.get("experience", [])[:3]
    ])
    critical_gaps = [g["skill"] for g in skill_gaps if g.get("severity") in ("critical", "high")]

    user_msg = f"""JOB: {jd_analysis.get('role_title', '')} at {jd_analysis.get('company_name', '')}
Seniority: {jd_analysis.get('seniority_level', '')}
Company stage: {jd_analysis.get('company_stage', 'Unknown')}
Expected culture: {jd_analysis.get('expected_resume_tone', '')}
Technical density: {jd_analysis.get('technical_density', '')}

Full JD analysis:
{json.dumps(jd_analysis, indent=2)}

Candidate background snapshot:
- Recent roles: {strengths_summary}
- Critical skill gaps: {', '.join(critical_gaps) or 'None identified'}

Extract hidden signals and provide strategic interview + career intel for this specific candidate."""

    return await call_claude_structured(
        system_prompt=_CAREER_INTEL_SYSTEM,
        user_message=user_msg,
        tool_name="career_intelligence",
        tool_description="Strategic career intel, interview prep, and negotiation advice",
        output_schema=_CAREER_INTEL_SCHEMA,
        max_tokens=3000,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR — Run all 4 agents in parallel
# ═══════════════════════════════════════════════════════════════════════════════

async def run_full_analysis(
    composition: dict,
    jd_analysis: dict,
    missing_keywords: list[str],
    progress_callback=None,
) -> dict:
    """
    Run all 4 RSEA sub-agents in parallel (asyncio.gather).
    progress_callback(agent_name, status) is called as each agent starts/completes.
    Returns the full career_report dict.
    """
    logger.info("RSEA: starting 4-agent parallel analysis")

    async def _with_progress(name: str, coro):
        if progress_callback:
            await progress_callback(name, "running")
        try:
            result = await coro
            if progress_callback:
                await progress_callback(name, "done")
            return result
        except Exception as exc:
            logger.error("RSEA sub-agent '%s' failed: %s", name, exc)
            if progress_callback:
                await progress_callback(name, "error")
            return None

    # Agent 1 runs first — learning_path needs its output
    # But to maximise parallelism, we run 1, 3, 4 together, then feed gaps into 2.
    # Actually for simplicity and max speed, run all 4 together.
    # Agent 2 gets a placeholder skill_gaps if agent 1 fails.

    skill_gap_coro = _with_progress(
        "skill_gap",
        _run_skill_gap_agent(composition, jd_analysis, missing_keywords),
    )
    resume_quality_coro = _with_progress(
        "resume_quality",
        _run_resume_quality_agent(composition, jd_analysis, missing_keywords),
    )

    # Run skill_gap and resume_quality in parallel first
    skill_gap_result, resume_quality_result = await asyncio.gather(
        skill_gap_coro, resume_quality_coro
    )

    skill_gaps = skill_gap_result.get("skill_gaps", []) if skill_gap_result else []

    # Now run learning_path (needs skill_gaps) and career_intel in parallel
    learning_path_coro = _with_progress(
        "learning_path",
        _run_learning_path_agent(skill_gaps, jd_analysis),
    )
    career_intel_coro = _with_progress(
        "career_intel",
        _run_career_intel_agent(composition, jd_analysis, skill_gaps),
    )

    learning_path_result, career_intel_result = await asyncio.gather(
        learning_path_coro, career_intel_coro
    )

    logger.info("RSEA: all 4 agents complete")

    return {
        "skill_gap": skill_gap_result,
        "learning_path": learning_path_result,
        "resume_quality": resume_quality_result,
        "career_intel": career_intel_result,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCEMENT — LLM-powered resume refinement (accepts user's chosen improvements)
# ═══════════════════════════════════════════════════════════════════════════════

_ENHANCE_SYSTEM = """You are a senior resume writer. Refine this resume composition based on the accepted improvements.

RULES:
- Do NOT invent facts, companies, technologies, or specific metrics
- You MAY add plausible scale estimates to bullets that clearly imply scale (e.g. 'built service' → 'built service handling ~50k daily requests')
- Weave missing keywords NATURALLY into bullets and summary — no keyword stuffing
- Strengthen weak bullets: action verb + context + measurable outcome
- Add leadership language where it fits organically
- Preserve all personal info, dates, companies, and education exactly
- Return the COMPLETE improved composition JSON"""

_ENHANCE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "personal": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}, "email": {"type": "string"},
                "phone": {"type": "string"}, "location": {"type": "string"},
                "linkedin": {"type": "string"}, "github": {"type": "string"},
                "website": {"type": "string"},
            },
            "required": ["name", "email"],
        },
        "summary": {"type": "string"},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"}, "company": {"type": "string"},
                    "location": {"type": "string"}, "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "company", "start_date", "end_date", "bullets"],
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                },
                "required": ["name", "bullets"],
            },
        },
        "skill_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["category", "items"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string"}, "field": {"type": "string"},
                    "institution": {"type": "string"}, "graduation_date": {"type": "string"},
                    "gpa": {"type": "string"}, "honors": {"type": "string"},
                },
                "required": ["degree", "institution", "graduation_date"],
            },
        },
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}, "issuer": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "section_order": {"type": "array", "items": {"type": "string"}},
        "layout": {
            "type": "object",
            "properties": {
                "max_pages": {"type": "integer"}, "density": {"type": "string"},
                "font_size_body": {"type": "integer"}, "font_size_name": {"type": "integer"},
                "margin_inches": {"type": "number"},
            },
        },
    },
    "required": ["personal", "experience", "section_order", "layout"],
}


async def enhance_composition(
    composition: dict,
    jd_analysis: dict,
    missing_keywords: list[str],
    accepted_improvements: list[dict],
) -> dict:
    """Apply accepted resume improvements via LLM. Returns refined composition dict."""
    rec_text = "\n".join(
        f"  [{r.get('type', '').upper()}] {r.get('title', '')}: {r.get('description', '')}"
        + (f"\n    Example fix: {r.get('example_fix', '')}" if r.get("example_fix") else "")
        + (f"\n    Keywords to add: {', '.join(r.get('keywords_to_add', []))}" if r.get("keywords_to_add") else "")
        for r in accepted_improvements
    )

    user_msg = f"""TARGET ROLE: {jd_analysis.get('role_title', '')} at {jd_analysis.get('company_name', '')}
Missing ATS keywords: {', '.join(missing_keywords[:20])}
Expected tone: {jd_analysis.get('expected_resume_tone', 'Technical')}

CURRENT COMPOSITION:
{json.dumps(composition, indent=2)}

ACCEPTED IMPROVEMENTS TO APPLY:
{rec_text}

Return the complete, enhanced composition with these improvements applied."""

    result = await call_claude_structured(
        system_prompt=_ENHANCE_SYSTEM,
        user_message=user_msg,
        tool_name="enhance_resume",
        tool_description="Enhanced resume composition with improvements applied",
        output_schema=_ENHANCE_OUTPUT_SCHEMA,
        max_tokens=8000,
    )

    # Safety net — LLM must never drop sections that exist in the original composition
    orig = composition  # alias for clarity

    if not result.get("certifications") and orig.get("certifications"):
        result["certifications"] = orig["certifications"]

    if not result.get("education") and orig.get("education"):
        result["education"] = orig["education"]

    if not result.get("skill_sections") and orig.get("skill_sections"):
        result["skill_sections"] = orig["skill_sections"]

    if not result.get("projects") and orig.get("projects"):
        result["projects"] = orig["projects"]

    if not result.get("summary") and orig.get("summary"):
        result["summary"] = orig["summary"]

    # Personal info: always preserve exactly from original — never trust LLM edits
    if orig.get("personal"):
        result["personal"] = orig["personal"]

    # Ensure section_order includes all populated sections
    _present = []
    for sec, key in [("summary", "summary"), ("experience", "experience"),
                     ("skills", "skill_sections"), ("projects", "projects"),
                     ("education", "education"), ("certifications", "certifications")]:
        if result.get(key):
            _present.append(sec)

    existing_order = result.get("section_order") or orig.get("section_order") or _present
    seen = set(existing_order)
    for sec in _present:
        if sec not in seen:
            existing_order.append(sec)
    result["section_order"] = existing_order

    return result
