"""
TopNotchResume — FastAPI Application Entry Point
Phase 2-4: Added SSE streaming, resume history, cover letter generation.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes.health import router as health_router
from app.api.routes.generate import router as generate_router
from app.api.routes.upload import router as upload_router
from app.api.routes.extract import router as extract_router
from app.api.routes.stream import router as stream_router
from app.api.routes.history import router as history_router
from app.api.routes.cover_letter import router as cover_letter_router
from app.api.routes.enhance import router as enhance_router
from app.api.routes.profile_restore import router as restore_router
from app.api.routes.refine import router as refine_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("TopNotchResume API v2 starting up — Phase 2-4 active")
    os.makedirs(settings.downloads_dir, exist_ok=True)

    # Initialise SQLite history DB
    try:
        from app.utils.db import init_db
        await init_db()
    except Exception as exc:
        logger.warning("DB init failed (non-fatal): %s", exc)

    # Initialise PostgreSQL Data Vault 2.0
    try:
        from app.utils.pg_store import init_pg
        await init_pg()
    except Exception as exc:
        logger.warning("PostgreSQL init failed (non-fatal): %s", exc)

    yield
    logger.info("TopNotchResume API shutting down")


app = FastAPI(
    title="TopNotchResume API",
    description="Enterprise-Grade AI Resume Intelligence & Dynamic Resume Generation Engine — v2",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core routes
app.include_router(health_router, tags=["Health"])
app.include_router(generate_router, prefix="/api", tags=["Resume"])
app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(extract_router, prefix="/api", tags=["Extract"])

# Phase 3 — streaming
app.include_router(stream_router, prefix="/api", tags=["Streaming"])

# Phase 4 — history + cover letter
app.include_router(history_router, prefix="/api", tags=["History"])
app.include_router(cover_letter_router, prefix="/api", tags=["Cover Letter"])

# Phase 5 — RSEA (Resume Shine Enhancer Agent)
app.include_router(enhance_router, prefix="/api", tags=["Enhance"])

# Phase 6 — PostgreSQL DV2 profile restore
app.include_router(restore_router, prefix="/api", tags=["Restore"])

# Phase 7 — Iterative quality check + refinement loop
app.include_router(refine_router, prefix="/api", tags=["Refine"])
