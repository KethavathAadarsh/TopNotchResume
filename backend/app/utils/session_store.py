"""
RSEA Session Store — in-memory store for Resume Shine Enhancer Agent sessions.

Session lifecycle:
  create_session()  → analysis_status: "pending"
  trigger_analysis() → analysis_status: "analyzing", agent_progress populated
  mark agents done  → career_report populated, analysis_status: "ready"
  generate enhanced → new version added, analysis_status reset to "pending" for re-analysis
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_sessions: dict[str, dict] = {}


def create_session(
    composition: dict,
    jd_analysis: dict,
    resume_format: str,
    v1_download_id: str,
    v1_filename: str,
    v1_ats_score: float,
    missing_keywords: list[str],
) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "composition": composition,
        "jd_analysis": jd_analysis,
        "resume_format": resume_format,
        "missing_keywords": missing_keywords,
        # Career intelligence report (populated by 4 parallel RSEA agents)
        "career_report": None,
        "analysis_status": "pending",   # pending | analyzing | ready | error
        "analysis_error": None,
        "agent_progress": {
            "skill_gap":      "pending",
            "resume_quality": "pending",
            "learning_path":  "pending",
            "career_intel":   "pending",
        },
        "versions": [
            {
                "version": 1,
                "download_id": v1_download_id,
                "filename": v1_filename,
                "ats_score": v1_ats_score,
                "created_at": _now(),
            }
        ],
        "created_at": _now(),
    }
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    return _sessions.get(session_id)


def update_session(session_id: str, updates: dict):
    if session_id in _sessions:
        _sessions[session_id].update(updates)


def set_agent_progress(session_id: str, agent: str, status: str):
    """Update a single agent's progress status."""
    if session_id in _sessions:
        _sessions[session_id]["agent_progress"][agent] = status


def add_version(
    session_id: str,
    download_id: str,
    filename: str,
    ats_score: float,
    missing_keywords: list[str],
) -> int:
    if session_id not in _sessions:
        return 0
    version_num = len(_sessions[session_id]["versions"]) + 1
    _sessions[session_id]["versions"].append({
        "version": version_num,
        "download_id": download_id,
        "filename": filename,
        "ats_score": ats_score,
        "created_at": _now(),
    })
    # Update missing_keywords for next analysis cycle
    _sessions[session_id]["missing_keywords"] = missing_keywords
    # Reset analysis so next GET re-analyses the improved composition
    _sessions[session_id]["analysis_status"] = "pending"
    _sessions[session_id]["career_report"] = None
    _sessions[session_id]["analysis_error"] = None
    _sessions[session_id]["agent_progress"] = {
        "skill_gap":      "pending",
        "resume_quality": "pending",
        "learning_path":  "pending",
        "career_intel":   "pending",
    }
    return version_num
