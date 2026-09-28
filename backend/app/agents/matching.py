"""
Match agent outputs back to the profile's experience entries.

Agents return per-role data (optimized bullets, relevance) as lists of dicts
with `title` and `company`. Keying those by company alone collides whenever a
candidate held several roles at one employer — every role then received the
last role's bullets. Lookups here use title+company first, and only fall back
to company or title when that fallback is unambiguous.
"""
from collections import defaultdict


def _norm(value) -> str:
    return (value or "").strip().lower() if isinstance(value, str) else ""


def exp_key(title, company) -> str:
    return f"{_norm(title)}|{_norm(company)}"


class RoleIndex:
    def __init__(self, entries):
        self._by_key: dict[str, dict] = {}
        self._by_company: dict[str, list[dict]] = defaultdict(list)
        self._by_title: dict[str, list[dict]] = defaultdict(list)
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            title, company = entry.get("title"), entry.get("company")
            self._by_key.setdefault(exp_key(title, company), entry)
            if _norm(company):
                self._by_company[_norm(company)].append(entry)
            if _norm(title):
                self._by_title[_norm(title)].append(entry)

    def __bool__(self) -> bool:
        return bool(self._by_key)

    def find(self, title, company) -> dict | None:
        exact = self._by_key.get(exp_key(title, company))
        if exact is not None:
            return exact
        by_company = self._by_company.get(_norm(company), [])
        if len(by_company) == 1:
            return by_company[0]
        by_title = self._by_title.get(_norm(title), [])
        if len(by_title) == 1:
            return by_title[0]
        return None
