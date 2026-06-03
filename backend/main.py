"""FastAPI application entry point."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from backend.core.config import get_settings
from backend.core.database import init_db, SessionLocal
from backend.routes.auth import router as auth_router
from backend.routes.events import router as events_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.admin import router as admin_router
from backend.services.scheduler import (
    start_scheduler, stop_scheduler, scheduler,
    get_scheduler_stats, _scheduler_stats,
)
from backend.models import Event, MonitorLog

settings = get_settings()

# Logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("Starting Lampung Infrastructure Monitor...")
    init_db()
    logger.info("Database initialized")

    # Start background scheduler
    start_scheduler()
    logger.info("Scheduler started")

    yield

    # Shutdown
    stop_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Sistem Pemantauan Infrastruktur Digital Provinsi Lampung",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# API routes
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(dashboard_router)
app.include_router(admin_router)


# Page routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "app_name": settings.APP_NAME})



@app.get("/health")
async def health():
    """Enhanced health check with scheduler and database status."""
    stats = get_scheduler_stats()
    db = SessionLocal()
    try:
        events_count = db.query(Event).count()
    except Exception:
        events_count = -1
    finally:
        db.close()

    # DB file size
    db_size_bytes = 0
    try:
        db_path = settings.database_path
        if db_path.exists():
            db_size_bytes = db_path.stat().st_size
    except Exception:
        pass

    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "server_status": "running",
        "scheduler_status": "running" if scheduler.running else "stopped",
        "telegram_status": "enabled" if settings.telegram_enabled else "disabled",
        "last_bmkg_success": stats.get("last_bmkg_success"),
        "last_news_success": stats.get("last_news_success"),
        "events_count": events_count,
        "db_size_bytes": db_size_bytes,
        "db_size_mb": db_size_mb,
        "bmkg_error_count": stats.get("bmkg_error_count", 0),
        "news_error_count": stats.get("news_error_count", 0),
        "scheduler_started_at": stats.get("started_at"),
    }


@app.get("/api/scheduler/status")
async def scheduler_status():
    """Detailed scheduler status: next runs, job history, error counts."""
    stats = get_scheduler_stats()

    # Build job details from APScheduler
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
            })

    # Recent job run history (last 10 per job)
    db = SessionLocal()
    history = {}
    try:
        for job_name in ("bmkg_check", "news_check", "daily_summary"):
            logs = (
                db.query(MonitorLog)
                .filter(MonitorLog.job_name == job_name)
                .order_by(MonitorLog.id.desc())
                .limit(10)
                .all()
            )
            history[job_name] = [log.to_dict() for log in logs]
    except Exception as e:
        logger.error("Failed to fetch job history: %s", e)
    finally:
        db.close()

    return {
        "scheduler_running": scheduler.running,
        "started_at": stats.get("started_at"),
        "jobs": jobs,
        "job_history": history,
        "error_counts": {
            "bmkg": stats.get("bmkg_error_count", 0),
            "news": stats.get("news_error_count", 0),
        },
        "retry_counts": {
            "bmkg": stats.get("bmkg_retry_count", 0),
            "news": stats.get("news_retry_count", 0),
        },
        "last_success": {
            "bmkg": stats.get("last_bmkg_success"),
            "news": stats.get("last_news_success"),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
