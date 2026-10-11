"""
Application entry-point.

On startup:
  - Creates all DB tables (idempotent via CREATE TABLE IF NOT EXISTS).
  - Seeds a default counsellor account so the system is usable out of the box.
    Username: admin_counsellor  |  Password: changeme123
  - Executes scheduled check for overdue follow-up check-ins.
  - Mounts static files and routes for Frontend (plain HTML/CSS/JS with Chart.js).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import User, UserRole
from app.routers import admin, alerts, auth, cases, checkins, dashboard, reports
from app.routers.admin import run_missed_followup_scan
from app.security import hash_password

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: runs setup on startup, teardown on shutdown."""
    await init_db()
    await _seed_default_counsellor()
    # Warm up NLP service so inferences respond instantly
    from app.ai.nlp_service import get_nlp_service
    get_nlp_service().analyze_text("System startup initialization test.")
    async with AsyncSessionLocal() as db:
        await run_missed_followup_scan(db)
    yield


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(checkins.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(reports.router)

# ── Static Files & HTML Page Handlers ─────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["frontend"])
async def index_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "MHM API active. Frontend index.html not found."}


@app.get("/victim", tags=["frontend"])
async def victim_page():
    victim_file = STATIC_DIR / "victim.html"
    if victim_file.exists():
        return FileResponse(victim_file)
    return {"message": "Victim portal active."}


@app.get("/dashboard", tags=["frontend"])
async def dashboard_page():
    dashboard_file = STATIC_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    return {"message": "Counsellor dashboard active."}


# ── Seed helper ───────────────────────────────────────────────────────────────

async def _seed_default_counsellor() -> None:
    """Insert a default counsellor if none exists yet."""
    seed_username = os.getenv("SEED_COUNSELLOR_USERNAME", "admin_counsellor")
    seed_password = os.getenv("SEED_COUNSELLOR_PASSWORD", "changeme123")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == seed_username)
        )
        if result.scalar_one_or_none() is None:
            counsellor = User(
                username=seed_username,
                password_hash=hash_password(seed_password),
                role=UserRole.counsellor,
            )
            db.add(counsellor)
            await db.commit()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}
