from app.engine.ats_engine import compute_ats_score


def _composition(bullets, skills=()):
    return {
        "summary": "",
        "experience": [{"title": "Engineer", "company": "Acme", "bullets": list(bullets)}],
        "skill_sections": [{"category": "Tech", "items": list(skills)}],
        "section_order": ["experience", "skills", "education"],
    }


def test_short_keywords_do_not_match_inside_other_words():
    comp = _composition(["Maintained Google integrations"])
    result = compute_ats_score(comp, {"ats_keywords": ["Go", "AI", "R"]})
    assert result["matched_keywords"] == []
    assert set(result["missing_keywords"]) == {"go", "ai", "r"}


def test_symbol_keywords_match_as_whole_terms():
    comp = _composition(["Built services in C++ and C# on .NET with CI/CD"])
    result = compute_ats_score(comp, {"ats_keywords": ["C++", "C#", ".NET", "CI/CD"]})
    assert set(result["matched_keywords"]) == {"c++", "c#", ".net", "ci/cd"}


def test_abbreviation_expansion_both_directions():
    comp = _composition(["Deployed on Kubernetes using machine learning models"])
    result = compute_ats_score(comp, {"ats_keywords": ["k8s", "ML"]})
    assert set(result["matched_keywords"]) == {"k8s", "ml"}


def test_whitespace_and_non_string_bullets_do_not_crash():
    comp = _composition(["   ", "Led migration", None, 42])
    result = compute_ats_score(comp, {"ats_keywords": ["migration"]})
    assert result["matched_keywords"] == ["migration"]


def test_duplicate_keywords_counted_once():
    comp = _composition(["Wrote Python"])
    result = compute_ats_score(comp, {"ats_keywords": ["Python", "python ", "PYTHON"]})
    assert result["matched_keywords"] == ["python"]
