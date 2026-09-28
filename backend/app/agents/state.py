"""
Shared LangGraph state that flows through all JARVIS agent nodes.
Each node receives the full state and returns a partial update dict.
"""
from typing import TypedDict, Optional, Any
from app.models.schema import GenerateRequest, ResumeComposition


class AgentState(TypedDict):
    request: GenerateRequest

    # Agent outputs — populated in order
    semantic_profile: Optional[dict[str, Any]]      # Profile Agent
    jd_analysis: Optional[dict[str, Any]]            # JD Agent
    relevance_map: Optional[dict[str, Any]]          # Relevance Agent
    optimized_content: Optional[dict[str, Any]]      # Optimizer Agent
    composition: Optional[dict[str, Any]]            # Composer Agent

    # Populated after composition
    ats_score: float
    keywords_matched: list[str]
    keywords_missing: list[str]

    errors: list[str]
    current_step: str
