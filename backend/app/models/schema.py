from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class ResumeFormat(str, Enum):
    ATS = "ats"
    EXECUTIVE = "executive"
    SWE = "swe"
    STARTUP = "startup"
    MINIMAL = "minimal"
    RESEARCH = "research"


class ExperienceEntry(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = "Present"
    location: Optional[str] = None
    bullets: List[str] = []

    @field_validator("bullets", mode="before")
    @classmethod
    def clean_bullets(cls, v):
        if not isinstance(v, list):
            return []
        return [b.strip() for b in v if isinstance(b, str) and b.strip()]


class ProjectEntry(BaseModel):
    name: str = ""
    description: str = ""
    technologies: List[str] = []
    bullets: List[str] = []
    url: Optional[str] = None
    github_url: Optional[str] = None

    @field_validator("technologies", "bullets", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if not isinstance(v, list):
            return []
        return [str(i).strip() for i in v if i]


class EducationEntry(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    graduation_date: str = ""
    gpa: Optional[str] = None
    honors: Optional[str] = None
    relevant_coursework: List[str] = []


class CertificationEntry(BaseModel):
    name: str = ""
    issuer: str = ""
    date: Optional[str] = None
    credential_id: Optional[str] = None


class SkillCategory(BaseModel):
    category: str = ""
    items: List[str] = []

    @field_validator("items", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if not isinstance(v, list):
            return []
        return [str(i).strip() for i in v if i]


class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    summary: Optional[str] = None
    experience: List[ExperienceEntry] = []
    projects: List[ProjectEntry] = []
    skill_categories: List[SkillCategory] = []
    flat_skills: List[str] = []
    education: List[EducationEntry] = []
    certifications: List[CertificationEntry] = []
    awards: List[str] = []
    publications: List[str] = []


class GenerateRequest(BaseModel):
    profile: CandidateProfile
    job_description: str
    format: ResumeFormat = ResumeFormat.ATS
    max_pages: int = Field(default=1, ge=1, le=2)
    target_role: Optional[str] = None
    quality_feedback: Optional[str] = None  # Injected by iterative refinement loop
    model: Optional[str] = None  # AI model override; falls back to ANTHROPIC_MODEL env var


class GenerateResponse(BaseModel):
    download_id: str
    ats_score: float
    keywords_matched: List[str]
    keywords_missing: List[str]
    sections_included: List[str]
    generation_time_ms: int


# Internal composition schemas used between agents

class ComposedExperience(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: str
    end_date: str
    bullets: List[str]
    relevance_score: float = 0.0


class ComposedProject(BaseModel):
    name: str
    description: str
    technologies: List[str] = []
    bullets: List[str]
    url: Optional[str] = None
    relevance_score: float = 0.0


class ComposedSection(BaseModel):
    section_type: str  # experience | skills | education | projects | certifications | summary
    title: str
    order: int


class LayoutConfig(BaseModel):
    max_pages: int = 1
    density: str = "high"  # high | medium | low
    font_size_body: int = 10
    font_size_name: int = 16
    margin_inches: float = 0.5


class ResumeComposition(BaseModel):
    personal: dict
    summary: Optional[str] = None
    experience: List[ComposedExperience] = []
    projects: List[ComposedProject] = []
    skill_categories: List[SkillCategory] = []
    education: List[EducationEntry] = []
    certifications: List[CertificationEntry] = []
    section_order: List[str] = ["summary", "experience", "skills", "projects", "education", "certifications"]
    layout: LayoutConfig = LayoutConfig()
