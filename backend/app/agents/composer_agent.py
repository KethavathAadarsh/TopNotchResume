"""
Agent 5 — Dynamic Resume Composition Agent
Makes all layout and prioritization decisions. Produces the final
ResumeComposition JSON that the DOCX engine renders directly.
"""
import json
import logging
from app.agents.state import AgentState
from app.utils.claude_client import call_claude_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Dynamic Resume Composition Agent within JARVIS, an enterprise-grade resume intelligence system.

You are the final intelligence layer before document rendering. Your decisions shape what the recruiter actually sees.

YOUR RESPONSIBILITIES:

1. SECTION ORDERING — decide the optimal section sequence for this specific role:
   - Technical roles: Experience → Skills → Projects → Education
   - Research roles: Publications/Research → Experience → Education
   - New grad: Education → Projects → Experience → Skills

2. BULLET COUNT PER ROLE — balance based on:
   - Recency (current role: 4-6 bullets, older roles: 2-3)
   - Relevance score (high-relevance roles get more bullets)
   - Page budget (1-page is ruthless; 2-page is more generous)

3. SKILLS SECTION FORMAT:
   - If categories exist: render as "Category: skill1, skill2, skill3"
   - Prioritize categories most relevant to the JD

4. PAGE-FIT STRATEGY for 1-page resumes:
   - Be aggressive: trim older role bullets to 2, omit pre-2015 roles entirely
   - Compress project descriptions to 1-2 bullets max
   - Truncate certifications to top 3 most relevant
   - Remove awards/publications unless directly relevant

5. SUMMARY — always include for Senior+ candidates; optional for Junior

CRITICAL RULES (non-negotiable):
- Use the EXACT bullets provided — they are pre-optimized. Do NOT rewrite them.
- Include ALL skill categories the user provided.
- Include ALL education entries.
- Include ALL certifications.
- Include ALL projects (for 1-page: trim bullets per project but keep all projects).
- Preserve exact company names, job titles, dates, and locations.
- The summary field must use the OPTIMIZED SUMMARY verbatim.

OUTPUT: A complete, ready-to-render ResumeComposition JSON."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "personal": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "location": {"type": "string"},
                "linkedin": {"type": "string"},
                "github": {"type": "string"},
                "website": {"type": "string"}
            },
            "required": ["name", "email"]
        },
        "summary": {"type": "string", "description": "Final professional summary or empty string"},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "company", "start_date", "end_date", "bullets"]
            }
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"}
                },
                "required": ["name", "bullets"]
            }
        },
        "skill_sections": {
            "type": "array",
            "description": "Ordered list of skill categories to render",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["category", "items"]
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "institution": {"type": "string"},
                    "graduation_date": {"type": "string"},
                    "gpa": {"type": "string"},
                    "honors": {"type": "string"}
                },
                "required": ["degree", "institution", "graduation_date"]
            }
        },
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "issuer": {"type": "string"},
                    "date": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "section_order": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ordered list of section names to render: summary | experience | skills | projects | education | certifications"
        },
        "layout": {
            "type": "object",
            "properties": {
                "max_pages": {"type": "integer"},
                "density": {"type": "string", "description": "high | medium | low"},
                "font_size_body": {"type": "integer"},
                "font_size_name": {"type": "integer"},
                "margin_inches": {"type": "number"}
            }
        }
    },
    "required": ["personal", "experience", "section_order", "layout"]
}


async def run_composer_agent(state: AgentState) -> dict:
    logger.info("Composer Agent: building final resume composition")
    profile = state["request"].profile
    optimized = state.get("optimized_content", {})
    relevance = state.get("relevance_map", {})
    jd = state.get("jd_analysis", {})
    semantic = state.get("semantic_profile", {})

    # Detect refinement mode early — drives bullet strategy below
    quality_feedback = getattr(state["request"], "quality_feedback", None)
    is_refinement = bool(quality_feedback)

    # ── Pre-merge: inject optimized bullets into original experience ──────────
    # Build lookup: company → optimized bullets (from Optimizer Agent)
    opt_exp_map: dict[str, list[str]] = {
        e["company"]: e.get("optimized_bullets", [])
        for e in optimized.get("optimized_experience", [])
    }
    # Also try title-based lookup as fallback (handles company-name mismatches)
    opt_exp_map_by_title: dict[str, list[str]] = {
        e["title"]: e.get("optimized_bullets", [])
        for e in optimized.get("optimized_experience", [])
    }

    # Build lookup: project name → optimized project data
    opt_proj_map: dict[str, dict] = {
        p["name"]: p
        for p in optimized.get("optimized_projects", [])
    }

    # Relevance ordering/filtering for experience
    experience_relevance = {
        e["company"]: e
        for e in relevance.get("experience_relevance", [])
    }
    ordered_experience = sorted(
        [e.model_dump() for e in profile.experience if
         not experience_relevance or experience_relevance.get(e.company, {}).get("include", True)],
        key=lambda e: experience_relevance.get(e["company"], {}).get("priority_rank", 99)
    )

    # Build a compound-key lookup (title|company) for original profile bullets.
    # Using title+company avoids collisions when multiple roles share the same company
    # (e.g. three roles all at "House of Code India Limited").
    _orig_by_compound: dict[str, list[str]] = {}
    for e in profile.experience:
        key = f"{e.title.lower().strip()}|{e.company.lower().strip()}"
        _orig_by_compound[key] = [b for b in e.bullets if b.strip()]

    def _orig_bullets(exp: dict) -> list[str]:
        """Return the original profile bullets for an experience entry."""
        key = f"{exp.get('title','').lower().strip()}|{exp.get('company','').lower().strip()}"
        # Try compound key first, then title-only, then company-only as fallback
        return (
            _orig_by_compound.get(key)
            or _orig_by_compound.get(f"{exp.get('title','').lower().strip()}|")
            or next(
                (v for k, v in _orig_by_compound.items()
                 if k.startswith(f"{exp.get('title','').lower().strip()}|")),
                []
            )
        )

    if is_refinement:
        # ADDITIVE REFINEMENT: keep the optimized bullets as the base (quality phrasing),
        # then APPEND any original profile bullets whose key phrases are not already present.
        # This preserves optimized language while ensuring nothing the user wrote is dropped
        # (e.g. "margin analyst agent", "bank reconciliation").
        for exp in ordered_experience:
            opt_b = (opt_exp_map.get(exp["company"], [])
                     or opt_exp_map_by_title.get(exp["title"], []))
            orig_b = _orig_bullets(exp)

            if opt_b and orig_b:
                opt_text = " ".join(opt_b).lower()
                additional = [
                    b for b in orig_b
                    if b.strip()
                    and " ".join(w for w in b.lower().split() if len(w) > 3)[:40] not in opt_text
                ]
                exp["bullets"] = opt_b + additional
            elif orig_b:
                exp["bullets"] = orig_b
            # else: keep whatever profile.experience had
            exp["bullets"] = [b for b in exp.get("bullets", []) if b.strip()]
    else:
        # Normal mode: inject optimized bullets — prefer company match, fall back to title match
        for exp in ordered_experience:
            ob = opt_exp_map.get(exp["company"], []) or opt_exp_map_by_title.get(exp["title"], [])
            if ob:
                exp["bullets"] = ob
            # Remove empty bullets from raw form input
            exp["bullets"] = [b for b in exp.get("bullets", []) if b.strip()]

    # ── Pre-merge: inject optimized bullets into all user projects ────────────
    merged_projects = []
    for p in profile.projects:
        proj = p.model_dump()
        opt_p = opt_proj_map.get(p.name)
        if opt_p:
            if opt_p.get("optimized_bullets"):
                proj["bullets"] = opt_p["optimized_bullets"]
            if opt_p.get("optimized_description"):
                proj["description"] = opt_p["optimized_description"]
        # Remove empty bullets
        proj["bullets"] = [b for b in proj.get("bullets", []) if b.strip()]
        merged_projects.append(proj)

    # Best summary: optimizer's → profile's → empty
    final_summary = (
        optimized.get("professional_summary")
        or profile.summary
        or ""
    )

    if is_refinement:
        density_instruction = "REFINEMENT MODE — do NOT trim bullets. Include every bullet EXACTLY as given. Page fit is secondary to completeness."
        rule7 = "7. REFINEMENT MODE: include ALL bullets for ALL experience entries — do NOT trim for page fit."
    else:
        density_instruction = f"DENSITY: {'high' if state['request'].max_pages == 1 else 'medium'}"
        rule7 = "7. For 1-page fit: trim bullets per entry (2-3 per old role) but never drop entire sections."

    user_message = f"""Build the final resume composition for rendering.

ALL DATA BELOW IS FINAL — DO NOT drop, skip, or modify any section the user provided.

TARGET: {jd.get('role_title', '')} at {jd.get('company_name', '')}
CANDIDATE LEVEL: {semantic.get('candidate_level', 'Senior')}
MAX PAGES: {state['request'].max_pages}
FORMAT: {state['request'].format.value}
{density_instruction}

OPTIMIZED SUMMARY (copy verbatim into the summary field):
{final_summary}

EXPERIENCE (use EVERY bullet EXACTLY as given, preserve all dates/locations/titles):
{json.dumps(ordered_experience, indent=2)}

PROJECTS (include ALL — use bullets exactly as given):
{json.dumps(merged_projects, indent=2)}

SKILL CATEGORIES (include ALL categories and ALL items within each):
{json.dumps([c.model_dump() for c in profile.skill_categories], indent=2)}

EDUCATION (include ALL entries):
{json.dumps([e.model_dump() for e in profile.education], indent=2)}

CERTIFICATIONS (include ALL entries):
{json.dumps([c.model_dump() for c in profile.certifications], indent=2)}

RELEVANCE MAP (use for section ordering only — never to drop sections or bullets):
{json.dumps(relevance, indent=2)}

JD CULTURE/TONE: {jd.get('expected_resume_tone', 'Balanced')}
COMPANY STAGE: {jd.get('company_stage', 'Unknown')}

RULES:
1. experience[].bullets must be the EXACT bullets from EXPERIENCE above — do not paraphrase or omit any.
2. skill_sections must contain EVERY category from SKILL CATEGORIES above.
3. education must contain EVERY entry from EDUCATION above.
4. certifications must contain EVERY entry from CERTIFICATIONS above.
5. projects must contain EVERY project from PROJECTS above.
6. section_order decides print order only — include all non-empty sections.
{rule7}
"""

    if quality_feedback:
        user_message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY FEEDBACK FROM PREVIOUS ITERATION — RESOLVE ALL BEFORE RENDERING:
{quality_feedback}

Every issue above MUST be corrected. Do NOT drop any section or bullet.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name="compose_resume",
            tool_description="Output the complete resume composition for DOCX rendering",
            output_schema=OUTPUT_SCHEMA,
            max_tokens=8000,
            model=state["request"].model,
        )

        # ── Safety net: override / fill critical fields directly from profile ─
        # Personal info: always use exact values — never trust LLM for these
        result["personal"] = {
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone or "",
            "location": profile.location or "",
            "linkedin": profile.linkedin or "",
            "github": profile.github or "",
            "website": profile.website or "",
        }

        # Summary: if LLM dropped it, use ours
        if not result.get("summary") and final_summary:
            result["summary"] = final_summary

        # Skills: fill from profile if missing OR if LLM returned categories with empty items
        raw_skills = result.get("skill_sections") or []
        valid_skills = [s for s in raw_skills if isinstance(s, dict) and s.get("items")]
        if len(valid_skills) < len(profile.skill_categories) and profile.skill_categories:
            result["skill_sections"] = [c.model_dump() for c in profile.skill_categories]

        # Education: if LLM dropped it, fill from profile
        if not result.get("education") and profile.education:
            result["education"] = [e.model_dump() for e in profile.education]

        # Certifications: if LLM dropped it, fill from profile
        if not result.get("certifications") and profile.certifications:
            result["certifications"] = [c.model_dump() for c in profile.certifications]

        # Projects: if LLM dropped all projects, restore merged set
        if not result.get("projects") and merged_projects:
            result["projects"] = merged_projects

        # Experience: if LLM dropped all experience, restore ordered set
        if not result.get("experience") and ordered_experience:
            result["experience"] = ordered_experience

        # Refinement safety net: restore bullets the LLM trimmed after the call.
        # Uses the same compound (title|company) key to avoid collisions between roles
        # that share a company name (e.g. multiple roles at the same consulting firm).
        if is_refinement and result.get("experience"):
            merged_by_compound = {
                f"{e['title'].lower().strip()}|{e['company'].lower().strip()}": e.get("bullets", [])
                for e in ordered_experience
            }
            for exp in result["experience"]:
                key = f"{exp.get('title','').lower().strip()}|{exp.get('company','').lower().strip()}"
                pre_llm = merged_by_compound.get(key, [])
                if pre_llm and len(exp.get("bullets", [])) < len(pre_llm):
                    exp["bullets"] = pre_llm

        # Section order: ensure all populated sections are listed
        _present = []
        if result.get("summary"):
            _present.append("summary")
        if result.get("experience"):
            _present.append("experience")
        if result.get("skill_sections"):
            _present.append("skills")
        if result.get("projects"):
            _present.append("projects")
        if result.get("education"):
            _present.append("education")
        if result.get("certifications"):
            _present.append("certifications")

        existing_order = result.get("section_order", [])
        # Keep LLM order where it includes the section; append any it missed
        seen = set(existing_order)
        for sec in _present:
            if sec not in seen:
                existing_order.append(sec)
        result["section_order"] = existing_order if existing_order else _present

        logger.info(
            "Composer Agent: sections=%s, experience=%d, projects=%d, skills=%d",
            result["section_order"],
            len(result.get("experience", [])),
            len(result.get("projects", [])),
            len(result.get("skill_sections", [])),
        )
        return {"composition": result, "current_step": "complete"}

    except Exception as e:
        logger.error("Composer Agent failed: %s", e)
        # Full fallback — build composition entirely from profile data
        fallback_experience = []
        for exp in ordered_experience:
            fallback_experience.append({
                "title": exp.get("title", ""),
                "company": exp.get("company", ""),
                "location": exp.get("location", ""),
                "start_date": exp.get("start_date", ""),
                "end_date": exp.get("end_date", "Present"),
                "bullets": [b for b in exp.get("bullets", []) if b.strip()],
            })

        fallback = {
            "personal": {
                "name": profile.name,
                "email": profile.email,
                "phone": profile.phone or "",
                "location": profile.location or "",
                "linkedin": profile.linkedin or "",
                "github": profile.github or "",
                "website": profile.website or "",
            },
            "summary": final_summary,
            "experience": fallback_experience,
            "projects": merged_projects,
            "skill_sections": [c.model_dump() for c in profile.skill_categories],
            "education": [e.model_dump() for e in profile.education],
            "certifications": [c.model_dump() for c in profile.certifications],
            "section_order": ["summary", "experience", "skills", "projects", "education", "certifications"],
            "layout": {"max_pages": state["request"].max_pages, "density": "high", "font_size_body": 10, "font_size_name": 16, "margin_inches": 0.5},
        }
        logger.warning("Composer Agent: using full profile fallback composition")
        return {
            "composition": fallback,
            "errors": state.get("errors", []) + [f"Composer agent: {e}"],
            "current_step": "complete",
        }
