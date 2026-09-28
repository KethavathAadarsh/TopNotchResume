import uuid

import pytest
from fastapi import HTTPException

from app.agents.matching import RoleIndex
from app.services.generation import DOWNLOADS_DIR, is_valid_id, resolve_download, safe_filename_stem
from app.utils.guards import SlidingWindowLimiter


@pytest.mark.parametrize("name,expected", [
    ("Ada Lovelace", "Ada_Lovelace"),
    ("../../etc/passwd", "etc_passwd"),
    ("..\\..\\windows", "windows"),
    ("", "resume"),
    ("日本語", "resume"),
])
def test_safe_filename_stem(name, expected):
    assert safe_filename_stem(name) == expected


def test_is_valid_id():
    assert is_valid_id(str(uuid.uuid4()))
    assert not is_valid_id("../../secret")
    assert not is_valid_id("")


def test_resolve_download_refuses_paths_outside_downloads_dir():
    download_id = str(uuid.uuid4())
    (DOWNLOADS_DIR / f"{download_id}.meta").write_text("../../escape.docx|||ats")
    assert resolve_download(download_id) is None


def test_role_index_keeps_same_company_roles_apart():
    index = RoleIndex([
        {"title": "Engineer", "company": "Acme", "optimized_bullets": ["A"]},
        {"title": "Senior Engineer", "company": "Acme", "optimized_bullets": ["B"]},
    ])
    assert index.find("Engineer", "Acme")["optimized_bullets"] == ["A"]
    assert index.find("senior engineer ", "ACME")["optimized_bullets"] == ["B"]
    # Company alone is ambiguous here — no guess
    assert index.find("Intern", "Acme") is None


def test_role_index_unambiguous_fallbacks():
    index = RoleIndex([{"title": "Engineer", "company": "Acme Inc", "x": 1}])
    assert index.find("Software Engineer", "Acme Inc")["x"] == 1  # by company
    assert index.find("Engineer", "Acme")["x"] == 1                # by title


def test_rate_limiter_blocks_then_isolates_keys():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    limiter.hit("a")
    limiter.hit("a")
    with pytest.raises(HTTPException) as exc:
        limiter.hit("a")
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
    limiter.hit("b")  # other clients unaffected
