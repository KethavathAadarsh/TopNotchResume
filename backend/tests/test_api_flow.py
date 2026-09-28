"""
End-to-end API flow with the Claude agents replaced by fakes: no network, no
API key spend. Exercises the real graph, SSE event log, DOCX storage, SQLite
artifacts, history scoping, restore, and cover letter lookup.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.agents import orchestrator


PROFILE = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "experience": [
        {"title": "Engineer", "company": "Acme", "start_date": "2019", "end_date": "2021",
         "bullets": ["worked on apis"]},
        {"title": "Senior Engineer", "company": "Acme", "start_date": "2021", "end_date": "Present",
         "bullets": ["led the platform team"]},
    ],
    "skill_categories": [{"category": "Languages", "items": ["Python", "Go"]}],
    "education": [{"institution": "UCL", "degree": "BSc", "graduation_date": "2019"}],
}
REQUEST = {"profile": PROFILE, "job_description": "We need a Python engineer. " * 5, "format": "swe"}


async def _fake_profile(state):
    return {"semantic_profile": {"candidate_level": "Senior"}}


async def _fake_jd(state):
    return {"jd_analysis": {"role_title": "Staff Engineer", "company_name": "Globex",
                            "ats_keywords": ["Python", "Go", "Rust"], "mandatory_skills": ["Python"]}}


async def _fake_relevance(state):
    return {"relevance_map": {"experience_relevance": [
        {"title": "Engineer", "company": "Acme", "include": True, "priority_rank": 2},
        {"title": "Senior Engineer", "company": "Acme", "include": True, "priority_rank": 1},
    ]}}


async def _fake_optimizer(state):
    return {"optimized_content": {
        "professional_summary": "Senior engineer.",
        "optimized_experience": [
            {"title": "Engineer", "company": "Acme", "optimized_bullets": ["Built REST APIs in Python"]},
            {"title": "Senior Engineer", "company": "Acme", "optimized_bullets": ["Led a platform team of 6"]},
        ],
    }}


@pytest.fixture
def client(monkeypatch):
    from app.agents import composer_agent

    async def fake_claude(**kwargs):
        # Composer echoes back what it was given, like the real prompt demands
        return {"personal": {}, "experience": [], "section_order": ["summary", "experience"], "layout": {}}

    monkeypatch.setattr(orchestrator, "run_profile_agent", _fake_profile)
    monkeypatch.setattr(orchestrator, "run_jd_agent", _fake_jd)
    monkeypatch.setattr(orchestrator, "run_relevance_agent", _fake_relevance)
    monkeypatch.setattr(orchestrator, "run_optimizer_agent", _fake_optimizer)
    monkeypatch.setattr(composer_agent, "call_claude_structured", fake_claude)
    monkeypatch.setattr(orchestrator, "jarvis", orchestrator._build_jarvis())

    from app.main import app
    with TestClient(app) as c:
        yield c


def _wait_for(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/generate/result/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_full_generation_flow(client):
    owner = {"X-Client-Id": str(uuid.uuid4())}
    stranger = {"X-Client-Id": str(uuid.uuid4())}

    job_id = client.post("/api/generate/async", json=REQUEST, headers=owner).json()["job_id"]
    body = _wait_for(client, job_id)
    assert body["status"] == "done", body
    result = body["result"]
    assert result["keywords_matched"] == ["python", "go"]  # whole-term: "go" found as its own word

    # Progress events arrive per agent, in pipeline order
    events = orchestrator.get_job(job_id)["events"]
    done_steps = [e["step"] for e in events if e["status"] == "done"]
    assert done_steps[:4] == ["parallel_init", "relevance", "optimize", "compose"]
    assert "render" in done_steps and done_steps[-1] == "complete"

    # DOCX is downloadable
    dl = client.get(f"/api/download/{result['download_id']}")
    assert dl.status_code == 200 and dl.content[:2] == b"PK"

    # History is scoped to the browser that generated it
    mine = client.get("/api/history", headers=owner).json()["items"]
    assert [i["id"] for i in mine] == [result["download_id"]]
    assert client.get("/api/history", headers=stranger).json()["items"] == []
    assert client.get("/api/history").json()["items"] == []

    # Restore works from SQLite (no PostgreSQL configured)
    restored = client.get(f"/api/history/{result['download_id']}/restore").json()
    assert restored["profile"]["name"] == "Ada Lovelace"
    assert restored["format"] == "swe"

    # Deleting needs the owner's ID
    client.delete(f"/api/history/{result['download_id']}", headers=stranger)
    assert len(client.get("/api/history", headers=owner).json()["items"]) == 1
    client.delete(f"/api/history/{result['download_id']}", headers=owner)
    assert client.get("/api/history", headers=owner).json()["items"] == []


def test_same_company_roles_keep_their_own_bullets(client):
    job_id = client.post("/api/generate/async", json=REQUEST).json()["job_id"]
    _wait_for(client, job_id)
    from app.utils.session_store import get_session
    session = get_session(orchestrator.get_job(job_id)["result"]["session_id"])
    bullets = {e["title"]: e["bullets"] for e in session["composition"]["experience"]}
    assert bullets == {
        "Senior Engineer": ["Led a platform team of 6"],
        "Engineer": ["Built REST APIs in Python"],
    }
    # priority_rank ordering respected
    assert [e["title"] for e in session["composition"]["experience"]] == ["Senior Engineer", "Engineer"]


def test_cover_letter_uses_stored_resume(client, monkeypatch):
    from app.api.routes import cover_letter

    seen = {}

    async def fake_letter(composition, jd_analysis, optimized_content):
        seen.update(composition=composition, jd=jd_analysis)
        return {"cover_letter": "Dear Globex", "subject_line": "Hi", "tone": "Technical"}

    monkeypatch.setattr(cover_letter, "generate_cover_letter", fake_letter)
    job_id = client.post("/api/generate/async", json=REQUEST).json()["job_id"]
    download_id = _wait_for(client, job_id)["result"]["download_id"]

    resp = client.post("/api/cover-letter", json={"download_id": download_id})
    assert resp.status_code == 200
    assert seen["composition"]["personal"]["name"] == "Ada Lovelace"
    assert seen["jd"]["company_name"] == "Globex"


def test_invalid_ids_rejected(client):
    assert client.get("/api/download/not-a-uuid").status_code == 400
    assert client.get(f"/api/download/{uuid.uuid4()}").status_code == 404
    assert client.post("/api/cover-letter", json={"download_id": "x"}).status_code == 400
