"""
AI Extraction endpoint.
POST /api/extract — accepts raw freeform text and a section name,
returns structured JSON ready to populate the form.
Supports section="all" to parse an entire resume at once.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from app.utils.claude_client import call_claude_structured
from app.utils.guards import limit_ai
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

SectionType = Literal["all", "personal", "experience", "projects", "skills", "education", "certifications"]

SYSTEM_PROMPT = """You are an intelligent resume parser. Extract structured data from any raw text the user provides.
The text may be:
- A pasted resume (PDF text, LinkedIn export, Word copy-paste)
- Freeform notes ("I worked at Google from 2019-2022, built APIs...")
- Bullet points, prose, or mixed format
- Partial information (only extract what's actually present)

Be accurate. Do not hallucinate details that are not in the text.
For dates, preserve whatever format is given (e.g. "Jan 2021", "2021", "January 2021 - Present").
For bullets/achievements: extract them verbatim — the user will optimize them later."""


# ── Section schemas ────────────────────────────────────────────────────────

PERSONAL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "location": {"type": "string"},
        "linkedin": {"type": "string"},
        "github": {"type": "string"},
        "website": {"type": "string"},
        "summary": {"type": "string"}
    }
}

EXPERIENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "location": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["company", "title", "start_date"]
            }
        }
    },
    "required": ["experience"]
}

PROJECTS_SCHEMA = {
    "type": "object",
    "properties": {
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                    "github_url": {"type": "string"}
                },
                "required": ["name"]
            }
        }
    },
    "required": ["projects"]
}

SKILLS_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["category", "items"]
            }
        },
        "flat_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills that don't fit a clear category"
        }
    },
    "required": ["skill_categories"]
}

EDUCATION_SCHEMA = {
    "type": "object",
    "properties": {
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "graduation_date": {"type": "string"},
                    "gpa": {"type": "string"},
                    "honors": {"type": "string"}
                },
                "required": ["institution", "degree"]
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
        }
    },
    "required": ["education"]
}

CERTIFICATIONS_SCHEMA = {
    "type": "object",
    "properties": {
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
        }
    },
    "required": ["certifications"]
}

ALL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "location": {"type": "string"},
        "linkedin": {"type": "string"},
        "github": {"type": "string"},
        "website": {"type": "string"},
        "summary": {"type": "string"},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "location": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["company", "title", "start_date"]
            }
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "technologies": {"type": "array", "items": {"type": "string"}},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                    "github_url": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "skill_categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["category", "items"]
            }
        },
        "flat_skills": {"type": "array", "items": {"type": "string"}},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "graduation_date": {"type": "string"},
                    "gpa": {"type": "string"},
                    "honors": {"type": "string"}
                },
                "required": ["institution", "degree"]
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
        }
    }
}

SECTION_CONFIG = {
    "personal":       (PERSONAL_SCHEMA,       "extract_personal",      "Extract personal contact info and summary"),
    "experience":     (EXPERIENCE_SCHEMA,      "extract_experience",    "Extract all work experience entries"),
    "projects":       (PROJECTS_SCHEMA,        "extract_projects",      "Extract all project entries"),
    "skills":         (SKILLS_SCHEMA,          "extract_skills",        "Extract skills, grouped by category where possible"),
    "education":      (EDUCATION_SCHEMA,       "extract_education",     "Extract education and certifications"),
    "certifications": (CERTIFICATIONS_SCHEMA,  "extract_certs",         "Extract certification entries"),
    "all":            (ALL_SCHEMA,             "extract_full_profile",  "Extract complete resume profile"),
}

SECTION_PROMPTS = {
    "personal":       "Extract the candidate's personal information and contact details.",
    "experience":     "Extract all work experience entries including company, title, dates, location, and achievements.",
    "projects":       "Extract all projects including name, technologies used, URLs, and key points.",
    "skills":         "Extract all skills. Group them by logical categories (Languages, Frameworks, Cloud, etc.).",
    "education":      "Extract education history and any certifications mentioned.",
    "certifications": "Extract all certifications, licenses, and credentials.",
    "all":            "Extract the complete resume — personal info, experience, projects, skills, education, and certifications.",
}


class ExtractRequest(BaseModel):
    section: SectionType
    raw_text: str


@router.post("/extract", dependencies=[Depends(limit_ai)])
async def extract_section(request: ExtractRequest):
    """
    Parse raw freeform text and return structured data for the given section.
    Use section='all' to extract an entire resume at once.
    """
    if not request.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required")

    if len(request.raw_text) > 30_000:
        raise HTTPException(status_code=400, detail="Text too long (max 30,000 characters)")

    schema, tool_name, tool_desc = SECTION_CONFIG[request.section]
    section_prompt = SECTION_PROMPTS[request.section]

    user_message = f"""Task: {section_prompt}

Raw text to parse:
---
{request.raw_text}
---

Extract all available information. Skip fields that are not present in the text."""

    try:
        result = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            tool_name=tool_name,
            tool_description=tool_desc,
            output_schema=schema,
            model=settings.anthropic_model,
            max_tokens=4096,
        )
        return {"section": request.section, "data": result}

    except Exception as e:
        logger.error("Extraction failed for section=%s: %s", request.section, e)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")
