"""
PostgreSQL Data Vault 2.0 Persistence Layer
============================================
Schema: dv (Data Vault 2.0)

Hubs      — core business entities (immutable, unique business keys)
Links     — relationships between hubs
Satellites — descriptive attributes (historized via load_dts / load_end_dts)
PIT       — Point-In-Time snapshot table (stores ACTUAL satellite timestamps
            for efficient single-query restore — never blindly stores "now")

Business Keys:
  hub_candidate  : candidate email (lowercased)
  hub_resume     : download_id (UUID)
  hub_job        : "<company>|<role_title>"

All hash keys are SHA-256 hex strings of the business key.
"""
import asyncpg
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
REC_SRC = "TOPNOTCH_RESUME"


# ── Hash helpers ─────────────────────────────────────────────────────────────

def _hk(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _diff(*values: Any) -> str:
    combined = "|".join(str(v or "") for v in values)
    return hashlib.sha256(combined.encode()).hexdigest()


def _parse_json(value: Any) -> Any:
    """Safely decode a JSONB column — handles both string and already-decoded types."""
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value  # asyncpg already decoded it
    try:
        return json.loads(value)
    except Exception:
        return []


# ── Pool management ──────────────────────────────────────────────────────────

async def init_pg() -> None:
    global _pool
    if not settings.database_url:
        logger.info("pg_store: DATABASE_URL not configured — skipping PostgreSQL init")
        return
    try:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        await _create_dv2_schema()
        logger.info("pg_store: Data Vault 2.0 schema ready")
    except Exception as exc:
        logger.error("pg_store: init failed — %s", exc)
        _pool = None


async def close_pg() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _available() -> bool:
    return _pool is not None


# ── Schema bootstrap ─────────────────────────────────────────────────────────

async def _create_dv2_schema() -> None:
    assert _pool
    ddl_statements = [
        "CREATE SCHEMA IF NOT EXISTS dv",
        # ── HUBS ──────────────────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS dv.hub_candidate (
            hub_candidate_hk    TEXT        PRIMARY KEY,
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            candidate_bk        TEXT        NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS dv.hub_resume (
            hub_resume_hk       TEXT        PRIMARY KEY,
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            resume_bk           TEXT        NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS dv.hub_job (
            hub_job_hk          TEXT        PRIMARY KEY,
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            job_bk              TEXT        NOT NULL
        )""",
        # ── LINKS ─────────────────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS dv.link_candidate_resume (
            link_hk             TEXT        PRIMARY KEY,
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            hub_resume_hk       TEXT        NOT NULL REFERENCES dv.hub_resume(hub_resume_hk)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.link_resume_job (
            link_hk             TEXT        PRIMARY KEY,
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hub_resume_hk       TEXT        NOT NULL REFERENCES dv.hub_resume(hub_resume_hk),
            hub_job_hk          TEXT        NOT NULL REFERENCES dv.hub_job(hub_job_hk)
        )""",
        # ── SATELLITES ────────────────────────────────────────────────────────
        """CREATE TABLE IF NOT EXISTS dv.sat_candidate_personal (
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            load_end_dts        TIMESTAMPTZ,
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            name                TEXT,
            phone               TEXT,
            location            TEXT,
            linkedin            TEXT,
            github              TEXT,
            website             TEXT,
            summary             TEXT,
            PRIMARY KEY (hub_candidate_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_candidate_experience (
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            load_end_dts        TIMESTAMPTZ,
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            experience_json     JSONB       NOT NULL DEFAULT '[]',
            PRIMARY KEY (hub_candidate_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_candidate_skills (
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            load_end_dts        TIMESTAMPTZ,
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            skill_categories    JSONB       NOT NULL DEFAULT '[]',
            flat_skills         JSONB       NOT NULL DEFAULT '[]',
            PRIMARY KEY (hub_candidate_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_candidate_projects (
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            load_end_dts        TIMESTAMPTZ,
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            projects_json       JSONB       NOT NULL DEFAULT '[]',
            PRIMARY KEY (hub_candidate_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_candidate_education (
            hub_candidate_hk    TEXT        NOT NULL REFERENCES dv.hub_candidate(hub_candidate_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            load_end_dts        TIMESTAMPTZ,
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            education_json      JSONB       NOT NULL DEFAULT '[]',
            certifications_json JSONB       NOT NULL DEFAULT '[]',
            PRIMARY KEY (hub_candidate_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_resume_generation (
            hub_resume_hk       TEXT        NOT NULL REFERENCES dv.hub_resume(hub_resume_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            ats_score           FLOAT,
            format              TEXT,
            max_pages           INTEGER,
            target_role         TEXT,
            session_id          TEXT,
            filename            TEXT,
            composition_json    JSONB,
            jd_analysis_json    JSONB,
            PRIMARY KEY (hub_resume_hk, load_dts)
        )""",
        """CREATE TABLE IF NOT EXISTS dv.sat_job_description (
            hub_job_hk          TEXT        NOT NULL REFERENCES dv.hub_job(hub_job_hk),
            load_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            rec_src             TEXT        NOT NULL DEFAULT 'TOPNOTCH_RESUME',
            hash_diff           TEXT        NOT NULL,
            company_name        TEXT,
            role_title          TEXT,
            job_description     TEXT,
            PRIMARY KEY (hub_job_hk, load_dts)
        )""",
        # ── PIT TABLE ─────────────────────────────────────────────────────────
        # Stores the ACTUAL satellite load_dts for each resume, enabling
        # point-in-time restore with a single-round-trip query set.
        """CREATE TABLE IF NOT EXISTS dv.pit_resume_snapshot (
            hub_resume_hk           TEXT        PRIMARY KEY REFERENCES dv.hub_resume(hub_resume_hk),
            snapshot_dts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            hub_candidate_hk        TEXT        REFERENCES dv.hub_candidate(hub_candidate_hk),
            hub_job_hk              TEXT        REFERENCES dv.hub_job(hub_job_hk),
            sat_personal_load_dts   TIMESTAMPTZ,
            sat_experience_load_dts TIMESTAMPTZ,
            sat_skills_load_dts     TIMESTAMPTZ,
            sat_projects_load_dts   TIMESTAMPTZ,
            sat_education_load_dts  TIMESTAMPTZ,
            sat_generation_load_dts TIMESTAMPTZ,
            sat_job_load_dts        TIMESTAMPTZ,
            job_description         TEXT,
            target_role             TEXT,
            format                  TEXT,
            max_pages               INTEGER
        )""",
        # ── INDEXES ───────────────────────────────────────────────────────────
        "CREATE INDEX IF NOT EXISTS idx_hub_resume_bk    ON dv.hub_resume(resume_bk)",
        "CREATE INDEX IF NOT EXISTS idx_hub_candidate_bk ON dv.hub_candidate(candidate_bk)",
        "CREATE INDEX IF NOT EXISTS idx_lcr_candidate    ON dv.link_candidate_resume(hub_candidate_hk)",
        "CREATE INDEX IF NOT EXISTS idx_lcr_resume       ON dv.link_candidate_resume(hub_resume_hk)",
        "CREATE INDEX IF NOT EXISTS idx_sat_gen_session  ON dv.sat_resume_generation(session_id)",
        # ── MIGRATIONS (idempotent) ────────────────────────────────────────────
        "ALTER TABLE dv.sat_resume_generation ADD COLUMN IF NOT EXISTS generation_ms INTEGER",
        "ALTER TABLE dv.sat_resume_generation ADD COLUMN IF NOT EXISTS kw_matched INTEGER",
        "ALTER TABLE dv.pit_resume_snapshot   ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE",
    ]
    async with _pool.acquire() as conn:
        async with conn.transaction():
            for stmt in ddl_statements:
                await conn.execute(stmt.strip())


# ── Satellite upsert helpers (each returns the actual current load_dts) ───────
# DV2 rule: only insert a new satellite row if hash_diff changed.
# The returned timestamp is the load_dts of whichever row is current
# (existing unchanged row OR the new row just inserted).
# The PIT table MUST use these returned timestamps — never blindly use "now".

async def _upsert_sat_personal(conn, hk, now, diff, name, phone, location, linkedin, github, website, summary) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_candidate_personal "
        "WHERE hub_candidate_hk=$1 AND load_end_dts IS NULL ORDER BY load_dts DESC LIMIT 1",
        hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    if row:
        await conn.execute(
            "UPDATE dv.sat_candidate_personal SET load_end_dts=$1 WHERE hub_candidate_hk=$2 AND load_end_dts IS NULL",
            now, hk,
        )
    await conn.execute(
        "INSERT INTO dv.sat_candidate_personal "
        "(hub_candidate_hk, load_dts, rec_src, hash_diff, name, phone, location, linkedin, github, website, summary) "
        "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
        hk, now, REC_SRC, diff, name, phone, location, linkedin, github, website, summary,
    )
    return now


async def _upsert_sat_experience(conn, hk, now, diff, experience) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_candidate_experience "
        "WHERE hub_candidate_hk=$1 AND load_end_dts IS NULL ORDER BY load_dts DESC LIMIT 1",
        hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    if row:
        await conn.execute(
            "UPDATE dv.sat_candidate_experience SET load_end_dts=$1 WHERE hub_candidate_hk=$2 AND load_end_dts IS NULL",
            now, hk,
        )
    await conn.execute(
        "INSERT INTO dv.sat_candidate_experience "
        "(hub_candidate_hk, load_dts, rec_src, hash_diff, experience_json) VALUES($1,$2,$3,$4,$5)",
        hk, now, REC_SRC, diff, json.dumps(experience),
    )
    return now


async def _upsert_sat_skills(conn, hk, now, diff, skill_categories, flat_skills) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_candidate_skills "
        "WHERE hub_candidate_hk=$1 AND load_end_dts IS NULL ORDER BY load_dts DESC LIMIT 1",
        hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    if row:
        await conn.execute(
            "UPDATE dv.sat_candidate_skills SET load_end_dts=$1 WHERE hub_candidate_hk=$2 AND load_end_dts IS NULL",
            now, hk,
        )
    await conn.execute(
        "INSERT INTO dv.sat_candidate_skills "
        "(hub_candidate_hk, load_dts, rec_src, hash_diff, skill_categories, flat_skills) VALUES($1,$2,$3,$4,$5,$6)",
        hk, now, REC_SRC, diff, json.dumps(skill_categories), json.dumps(flat_skills),
    )
    return now


async def _upsert_sat_projects(conn, hk, now, diff, projects) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_candidate_projects "
        "WHERE hub_candidate_hk=$1 AND load_end_dts IS NULL ORDER BY load_dts DESC LIMIT 1",
        hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    if row:
        await conn.execute(
            "UPDATE dv.sat_candidate_projects SET load_end_dts=$1 WHERE hub_candidate_hk=$2 AND load_end_dts IS NULL",
            now, hk,
        )
    await conn.execute(
        "INSERT INTO dv.sat_candidate_projects "
        "(hub_candidate_hk, load_dts, rec_src, hash_diff, projects_json) VALUES($1,$2,$3,$4,$5)",
        hk, now, REC_SRC, diff, json.dumps(projects),
    )
    return now


async def _upsert_sat_education(conn, hk, now, diff, education, certifications) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_candidate_education "
        "WHERE hub_candidate_hk=$1 AND load_end_dts IS NULL ORDER BY load_dts DESC LIMIT 1",
        hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    if row:
        await conn.execute(
            "UPDATE dv.sat_candidate_education SET load_end_dts=$1 WHERE hub_candidate_hk=$2 AND load_end_dts IS NULL",
            now, hk,
        )
    await conn.execute(
        "INSERT INTO dv.sat_candidate_education "
        "(hub_candidate_hk, load_dts, rec_src, hash_diff, education_json, certifications_json) VALUES($1,$2,$3,$4,$5,$6)",
        hk, now, REC_SRC, diff, json.dumps(education), json.dumps(certifications),
    )
    return now


async def _upsert_sat_job(conn, job_hk, now, diff, company_name, role_title, job_description) -> datetime:
    row = await conn.fetchrow(
        "SELECT hash_diff, load_dts FROM dv.sat_job_description "
        "WHERE hub_job_hk=$1 ORDER BY load_dts DESC LIMIT 1",
        job_hk,
    )
    if row and row["hash_diff"] == diff:
        return row["load_dts"]
    await conn.execute(
        "INSERT INTO dv.sat_job_description "
        "(hub_job_hk, load_dts, rec_src, hash_diff, company_name, role_title, job_description) "
        "VALUES($1,$2,$3,$4,$5,$6,$7)",
        job_hk, now, REC_SRC, diff, company_name, role_title, job_description,
    )
    return now


# ── Write path ───────────────────────────────────────────────────────────────

async def save_generation(
    *,
    email: str,
    name: str,
    phone: str,
    location: str,
    linkedin: str,
    github: str,
    website: str,
    summary: str,
    experience: list[dict],
    skill_categories: list[dict],
    flat_skills: list[str],
    projects: list[dict],
    education: list[dict],
    certifications: list[dict],
    job_description: str,
    company_name: str,
    role_title: str,
    target_role: str,
    format: str,
    max_pages: int,
    download_id: str,
    session_id: str | None,
    filename: str,
    ats_score: float,
    composition: dict,
    jd_analysis: dict,
    generation_ms: int = 0,
    kw_matched: int = 0,
) -> None:
    if not _available():
        return

    now = datetime.now(timezone.utc)
    candidate_hk = _hk(email)
    resume_hk = _hk(download_id)
    job_bk = f"{company_name}|{role_title}"
    job_hk = _hk(job_bk)

    diff_personal  = _diff(name, phone, location, linkedin, github, website, summary)
    diff_exp       = _diff(json.dumps(experience, sort_keys=True))
    diff_skills    = _diff(json.dumps(skill_categories, sort_keys=True), json.dumps(flat_skills))
    diff_projects  = _diff(json.dumps(projects, sort_keys=True))
    diff_edu       = _diff(json.dumps(education, sort_keys=True), json.dumps(certifications, sort_keys=True))
    diff_job       = _diff(company_name, role_title, job_description)

    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():

                # ── Hubs (idempotent) ─────────────────────────────────────────
                await conn.execute(
                    "INSERT INTO dv.hub_candidate(hub_candidate_hk, load_dts, rec_src, candidate_bk) "
                    "VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                    candidate_hk, now, REC_SRC, email.lower().strip(),
                )
                await conn.execute(
                    "INSERT INTO dv.hub_resume(hub_resume_hk, load_dts, rec_src, resume_bk) "
                    "VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                    resume_hk, now, REC_SRC, download_id,
                )
                await conn.execute(
                    "INSERT INTO dv.hub_job(hub_job_hk, load_dts, rec_src, job_bk) "
                    "VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                    job_hk, now, REC_SRC, job_bk,
                )

                # ── Links (idempotent) ────────────────────────────────────────
                lcr_hk = _hk(candidate_hk + resume_hk)
                await conn.execute(
                    "INSERT INTO dv.link_candidate_resume(link_hk, load_dts, rec_src, hub_candidate_hk, hub_resume_hk) "
                    "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
                    lcr_hk, now, REC_SRC, candidate_hk, resume_hk,
                )
                lrj_hk = _hk(resume_hk + job_hk)
                await conn.execute(
                    "INSERT INTO dv.link_resume_job(link_hk, load_dts, rec_src, hub_resume_hk, hub_job_hk) "
                    "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
                    lrj_hk, now, REC_SRC, resume_hk, job_hk,
                )

                # ── Satellites — upsert, each returns ACTUAL current load_dts ──
                personal_dts = await _upsert_sat_personal(
                    conn, candidate_hk, now, diff_personal,
                    name, phone, location, linkedin, github, website, summary,
                )
                exp_dts = await _upsert_sat_experience(conn, candidate_hk, now, diff_exp, experience)
                skills_dts = await _upsert_sat_skills(conn, candidate_hk, now, diff_skills, skill_categories, flat_skills)
                projects_dts = await _upsert_sat_projects(conn, candidate_hk, now, diff_projects, projects)
                edu_dts = await _upsert_sat_education(conn, candidate_hk, now, diff_edu, education, certifications)
                job_dts = await _upsert_sat_job(conn, job_hk, now, diff_job, company_name, role_title, job_description)

                # Resume generation satellite — always new (one row per resume)
                await conn.execute(
                    """INSERT INTO dv.sat_resume_generation
                       (hub_resume_hk, load_dts, rec_src, ats_score, format, max_pages,
                        target_role, session_id, filename, composition_json, jd_analysis_json,
                        generation_ms, kw_matched)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT DO NOTHING""",
                    resume_hk, now, REC_SRC, ats_score, format, max_pages,
                    target_role, session_id, filename,
                    json.dumps(composition), json.dumps(jd_analysis),
                    generation_ms, kw_matched,
                )

                # ── PIT snapshot — uses ACTUAL satellite timestamps ────────────
                # If a satellite had no change its load_dts may be earlier than now.
                # We store the real timestamp so get_restore_data can find the row.
                await conn.execute(
                    """INSERT INTO dv.pit_resume_snapshot
                       (hub_resume_hk, snapshot_dts, hub_candidate_hk, hub_job_hk,
                        sat_personal_load_dts, sat_experience_load_dts, sat_skills_load_dts,
                        sat_projects_load_dts, sat_education_load_dts, sat_generation_load_dts,
                        sat_job_load_dts, job_description, target_role, format, max_pages)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                       ON CONFLICT DO NOTHING""",
                    resume_hk, now, candidate_hk, job_hk,
                    personal_dts, exp_dts, skills_dts, projects_dts, edu_dts, now, job_dts,
                    job_description, target_role, format, max_pages,
                )

        logger.info("pg_store: saved generation download_id=%s candidate=%s", download_id, email)

    except Exception as exc:
        logger.error("pg_store: save_generation failed — %s", exc)


# ── Read path ────────────────────────────────────────────────────────────────

async def get_composition(download_id: str) -> dict | None:
    """Retrieve the stored composition JSON for a given download_id."""
    if not _available():
        return None
    resume_hk = _hk(download_id)
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT composition_json FROM dv.sat_resume_generation "
                "WHERE hub_resume_hk=$1 ORDER BY load_dts DESC LIMIT 1",
                resume_hk,
            )
            if not row or row["composition_json"] is None:
                return None
            val = row["composition_json"]
            if isinstance(val, dict):
                return val
            try:
                result = json.loads(val)
                return result if isinstance(result, dict) else None
            except Exception:
                return None
    except Exception as exc:
        logger.error("pg_store: get_composition failed download_id=%s — %s", download_id, exc)
        return None


async def get_history_pg(limit: int = 50) -> list[dict]:
    """Return recent resume generations ordered by newest first."""
    if not _available():
        return []
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    hr.resume_bk                                        AS id,
                    pit.snapshot_dts                                    AS created_at,
                    COALESCE(sp.name,   '')                             AS candidate,
                    COALESCE(sj.role_title,   '')                       AS role,
                    COALESCE(sj.company_name, '')                       AS company,
                    COALESCE(sg.format,  'ats')                         AS format,
                    COALESCE(sg.ats_score, 0.0)                         AS ats_score,
                    COALESCE(sg.kw_matched, 0)                          AS kw_matched,
                    COALESCE(sg.generation_ms, 0)                       AS gen_ms,
                    COALESCE(sg.filename, '')                           AS filename,
                    sg.session_id
                FROM dv.hub_resume hr
                JOIN dv.pit_resume_snapshot pit
                    ON pit.hub_resume_hk = hr.hub_resume_hk
                LEFT JOIN dv.link_candidate_resume lcr
                    ON lcr.hub_resume_hk = hr.hub_resume_hk
                LEFT JOIN dv.sat_candidate_personal sp
                    ON sp.hub_candidate_hk = lcr.hub_candidate_hk
                    AND sp.load_dts = pit.sat_personal_load_dts
                LEFT JOIN dv.sat_resume_generation sg
                    ON sg.hub_resume_hk = hr.hub_resume_hk
                    AND sg.load_dts = pit.sat_generation_load_dts
                LEFT JOIN dv.sat_job_description sj
                    ON sj.hub_job_hk = pit.hub_job_hk
                    AND sj.load_dts = pit.sat_job_load_dts
                WHERE NOT COALESCE(pit.is_deleted, FALSE)
                ORDER BY pit.snapshot_dts DESC
                LIMIT $1
                """,
                limit,
            )
            return [
                {
                    "id":         r["id"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else "",
                    "candidate":  r["candidate"],
                    "role":       r["role"],
                    "company":    r["company"],
                    "format":     r["format"],
                    "ats_score":  float(r["ats_score"]),
                    "kw_matched": int(r["kw_matched"]),
                    "gen_ms":     int(r["gen_ms"]),
                    "filename":   r["filename"],
                    "session_id": r["session_id"],
                }
                for r in rows
            ]
    except Exception as exc:
        logger.error("pg_store: get_history_pg failed — %s", exc)
        return []


async def delete_history_pg(download_id: str) -> None:
    """Soft-delete a resume from history (sets is_deleted=TRUE on the PIT row)."""
    if not _available():
        return
    resume_hk = _hk(download_id)
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE dv.pit_resume_snapshot SET is_deleted = TRUE WHERE hub_resume_hk = $1",
                resume_hk,
            )
    except Exception as exc:
        logger.error("pg_store: delete_history_pg failed download_id=%s — %s", download_id, exc)


async def get_restore_data(download_id: str) -> dict | None:
    if not _available():
        return None

    resume_hk = _hk(download_id)

    try:
        async with _pool.acquire() as conn:
            pit = await conn.fetchrow(
                "SELECT * FROM dv.pit_resume_snapshot WHERE hub_resume_hk=$1",
                resume_hk,
            )
            if not pit:
                return None

            candidate_hk = pit["hub_candidate_hk"]

            # Load each satellite at the PIT-recorded timestamp
            personal = await conn.fetchrow(
                "SELECT * FROM dv.sat_candidate_personal WHERE hub_candidate_hk=$1 AND load_dts=$2",
                candidate_hk, pit["sat_personal_load_dts"],
            ) if pit["sat_personal_load_dts"] else None

            exp_row = await conn.fetchrow(
                "SELECT experience_json FROM dv.sat_candidate_experience WHERE hub_candidate_hk=$1 AND load_dts=$2",
                candidate_hk, pit["sat_experience_load_dts"],
            ) if pit["sat_experience_load_dts"] else None

            skills_row = await conn.fetchrow(
                "SELECT skill_categories, flat_skills FROM dv.sat_candidate_skills WHERE hub_candidate_hk=$1 AND load_dts=$2",
                candidate_hk, pit["sat_skills_load_dts"],
            ) if pit["sat_skills_load_dts"] else None

            proj_row = await conn.fetchrow(
                "SELECT projects_json FROM dv.sat_candidate_projects WHERE hub_candidate_hk=$1 AND load_dts=$2",
                candidate_hk, pit["sat_projects_load_dts"],
            ) if pit["sat_projects_load_dts"] else None

            edu_row = await conn.fetchrow(
                "SELECT education_json, certifications_json FROM dv.sat_candidate_education WHERE hub_candidate_hk=$1 AND load_dts=$2",
                candidate_hk, pit["sat_education_load_dts"],
            ) if pit["sat_education_load_dts"] else None

            gen_row = await conn.fetchrow(
                "SELECT ats_score, format, max_pages, target_role, session_id FROM dv.sat_resume_generation "
                "WHERE hub_resume_hk=$1 AND load_dts=$2",
                resume_hk, pit["sat_generation_load_dts"],
            ) if pit["sat_generation_load_dts"] else None

            # Resolve email from hub
            email_row = await conn.fetchrow(
                """SELECT hc.candidate_bk FROM dv.link_candidate_resume lcr
                   JOIN dv.hub_candidate hc ON hc.hub_candidate_hk = lcr.hub_candidate_hk
                   WHERE lcr.hub_resume_hk=$1 LIMIT 1""",
                resume_hk,
            )
            candidate_email = email_row["candidate_bk"] if email_row else ""

        profile: dict = {
            "name":             personal["name"]     if personal else "",
            "email":            candidate_email,
            "phone":            personal["phone"]    if personal else "",
            "location":         personal["location"] if personal else "",
            "linkedin":         personal["linkedin"] if personal else "",
            "github":           personal["github"]   if personal else "",
            "website":          personal["website"]  if personal else "",
            "summary":          personal["summary"]  if personal else "",
            "experience":       _parse_json(exp_row["experience_json"])     if exp_row else [],
            "skill_categories": _parse_json(skills_row["skill_categories"]) if skills_row else [],
            "flat_skills":      _parse_json(skills_row["flat_skills"])      if skills_row else [],
            "projects":         _parse_json(proj_row["projects_json"])      if proj_row else [],
            "education":        _parse_json(edu_row["education_json"])      if edu_row else [],
            "certifications":   _parse_json(edu_row["certifications_json"]) if edu_row else [],
            "awards":           [],
            "publications":     [],
        }

        return {
            "profile":         profile,
            "job_description": pit["job_description"] or "",
            "target_role":     (pit["target_role"] or (gen_row["target_role"] if gen_row else "")) or "",
            "format":          (pit["format"] or (gen_row["format"] if gen_row else "")) or "ats",
            "max_pages":       pit["max_pages"] or (gen_row["max_pages"] if gen_row else 1) or 1,
            "ats_score":       float(gen_row["ats_score"]) if gen_row and gen_row["ats_score"] else 0.0,
            "session_id":      gen_row["session_id"] if gen_row else None,
        }

    except Exception as exc:
        logger.error("pg_store: get_restore_data failed download_id=%s — %s", download_id, exc)
        return None
