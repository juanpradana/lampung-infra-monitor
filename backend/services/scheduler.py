"""Background scheduler for monitoring jobs."""
import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.models import Event, Alert, MonitorLog
from backend.services.bmkg import fetch_latest_earthquake, fetch_recent_earthquakes
from backend.services.news_rss import fetch_all_news
from backend.services.telegram_bot import create_notifier

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()

# Hard timeouts for each job (seconds). If a job exceeds this, it is killed.
BMKG_JOB_TIMEOUT = 60   # BMKG has 2 HTTP calls, each 10s max → 60s hard limit
NEWS_JOB_TIMEOUT = 300  # News has 35+ HTTP calls → 5 min hard limit
SUMMARY_JOB_TIMEOUT = 30

# Watchdog: mark any 'running' log older than this as 'failed'
STALE_LOG_TIMEOUT = 120  # 2 minutes


def is_in_lampung(lat: float, lon: float) -> bool:
    """Check if coordinates are within Lampung bounding box."""
    return (
        settings.LAMPUNG_LAT_MIN <= lat <= settings.LAMPUNG_LAT_MAX
        and settings.LAMPUNG_LON_MIN <= lon <= settings.LAMPUNG_LON_MAX
    )


async def save_event(event_data: dict, db) -> bool:
    """Save an event if it doesn't already exist."""
    source_id = event_data.get("source_id")
    if source_id:
        existing = db.query(Event).filter(Event.source_id == source_id).first()
        if existing:
            return False

    event = Event(
        title=event_data.get("title", ""),
        description=event_data.get("description", ""),
        category=event_data.get("category", "lainnya"),
        severity=event_data.get("severity", "medium"),
        status="active",
        source=event_data.get("source", "Unknown"),
        source_url=event_data.get("source_url", ""),
        source_id=source_id,
        province=event_data.get("province", "Lampung"),
        kabupaten=event_data.get("kabupaten"),
        kecamatan=event_data.get("kecamatan"),
        latitude=event_data.get("latitude"),
        longitude=event_data.get("longitude"),
        occurred_at=event_data.get("occurred_at"),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return True


def _safe_commit(db, context: str):
    """Commit with fallback — log error but never raise."""
    try:
        db.commit()
    except Exception as e:
        logger.error(f"DB commit failed ({context}): {e}")
        try:
            db.rollback()
        except Exception:
            pass


def cleanup_stale_logs():
    """Mark any 'running' monitor logs older than STALE_LOG_TIMEOUT as 'failed'.

    This is a synchronous helper called at job-start time before each job
    executes, so it runs outside the async timeout wrapper.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).timestamp() - STALE_LOG_TIMEOUT
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
        stale = (
            db.query(MonitorLog)
            .filter(
                MonitorLog.status == "running",
                MonitorLog.started_at < cutoff_dt,
            )
            .all()
        )
        if stale:
            for log in stale:
                log.status = "failed"
                log.error_message = "Timed out — job exceeded watchdog threshold"
                log.finished_at = datetime.now(timezone.utc)
            _safe_commit(db, "cleanup_stale_logs")
            logger.warning(
                "Watchdog: marked %d stale 'running' log(s) as 'failed'", len(stale)
            )
    except Exception as e:
        logger.error(f"Watchdog cleanup error: {e}")
    finally:
        db.close()


# ── BMKG Job ────────────────────────────────────────────────────────────

async def _bmkg_job_inner():
    """Core BMKG check logic (runs inside timeout wrapper)."""
    logger.info("Running BMKG check...")
    db = SessionLocal()
    notifier = create_notifier()
    log = MonitorLog(job_name="bmkg_check", started_at=datetime.now(timezone.utc))
    db.add(log)
    _safe_commit(db, "bmkg_check: create log")

    try:
        events_found = 0
        alerts_sent = 0

        # Fetch latest earthquake
        latest = await fetch_latest_earthquake()
        if latest and latest.get("latitude"):
            if is_in_lampung(latest["latitude"], latest["longitude"]):
                latest["category"] = "bencana"
                latest["severity"] = "high"
                latest["source_id"] = f"bmkg-gempa-{latest.get('occurred_at', '')}"
                saved = await save_event(latest, db)
                if saved:
                    events_found += 1
                    if notifier.enabled:
                        await notifier.send_event_alert(latest)
                        alerts_sent += 1

        # Fetch recent felt earthquakes
        recent = await fetch_recent_earthquakes()
        for eq in recent:
            if eq.get("latitude") and is_in_lampung(eq["latitude"], eq["longitude"]):
                eq["category"] = "bencana"
                eq["severity"] = "medium"
                eq["source_id"] = f"bmkg-dirasakan-{eq.get('occurred_at', '')}"
                saved = await save_event(eq, db)
                if saved:
                    events_found += 1
                    if notifier.enabled:
                        await notifier.send_event_alert(eq)
                        alerts_sent += 1

        log.status = "success"
        log.events_found = events_found
        log.alerts_sent = alerts_sent
        log.finished_at = datetime.now(timezone.utc)
        _safe_commit(db, "bmkg_check: success")
        logger.info(
            "BMKG check done: %d events found, %d alerts sent", events_found, alerts_sent
        )

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.now(timezone.utc)
        _safe_commit(db, "bmkg_check: failed")
        logger.error("BMKG check failed: %s", e)
    finally:
        db.close()


async def job_check_bmkg():
    """BMKG monitoring job — wrapped with hard timeout."""
    cleanup_stale_logs()
    try:
        await asyncio.wait_for(_bmkg_job_inner(), timeout=BMKG_JOB_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error(
            "BMKG check TIMED OUT after %ds — job killed", BMKG_JOB_TIMEOUT
        )
        # Try to update the log entry to 'failed'
        db = SessionLocal()
        try:
            log = (
                db.query(MonitorLog)
                .filter(
                    MonitorLog.job_name == "bmkg_check",
                    MonitorLog.status == "running",
                )
                .order_by(MonitorLog.id.desc())
                .first()
            )
            if log:
                log.status = "failed"
                log.error_message = f"Hard timeout after {BMKG_JOB_TIMEOUT}s"
                log.finished_at = datetime.now(timezone.utc)
                _safe_commit(db, "bmkg_check: timeout update")
        except Exception as e:
            logger.error("Failed to update timeout log: %s", e)
        finally:
            db.close()
    except Exception as e:
        logger.error("BMKG check unexpected error: %s", e)
        # Ensure log is marked failed even for unexpected errors
        db = SessionLocal()
        try:
            log = (
                db.query(MonitorLog)
                .filter(
                    MonitorLog.job_name == "bmkg_check",
                    MonitorLog.status == "running",
                )
                .order_by(MonitorLog.id.desc())
                .first()
            )
            if log:
                log.status = "failed"
                log.error_message = f"Unexpected error: {str(e)[:500]}"
                log.finished_at = datetime.now(timezone.utc)
                _safe_commit(db, "bmkg_check: unexpected error update")
        except Exception:
            pass
        finally:
            db.close()


# ── News Job ─────────────────────────────────────────────────────────────

async def _news_job_inner():
    """Core news check logic (runs inside timeout wrapper)."""
    logger.info("Running news check...")
    db = SessionLocal()
    notifier = create_notifier()
    log = MonitorLog(job_name="news_check", started_at=datetime.now(timezone.utc))
    db.add(log)
    _safe_commit(db, "news_check: create log")

    try:
        news_items = await fetch_all_news()
        events_found = 0
        alerts_sent = 0

        for item in news_items:
            saved = await save_event(item, db)
            if saved:
                events_found += 1
                # Only alert for high/critical severity
                if item.get("severity") in ("high", "critical"):
                    if notifier.enabled:
                        await notifier.send_event_alert(item)
                        alerts_sent += 1

        log.status = "success"
        log.events_found = events_found
        log.alerts_sent = alerts_sent
        log.finished_at = datetime.now(timezone.utc)
        _safe_commit(db, "news_check: success")
        logger.info(
            "News check done: %d events found, %d alerts sent", events_found, alerts_sent
        )

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.now(timezone.utc)
        _safe_commit(db, "news_check: failed")
        logger.error("News check failed: %s", e)
    finally:
        db.close()


async def job_check_news():
    """News monitoring job — wrapped with hard timeout."""
    cleanup_stale_logs()
    try:
        await asyncio.wait_for(_news_job_inner(), timeout=NEWS_JOB_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error(
            "News check TIMED OUT after %ds — job killed", NEWS_JOB_TIMEOUT
        )
        db = SessionLocal()
        try:
            log = (
                db.query(MonitorLog)
                .filter(
                    MonitorLog.job_name == "news_check",
                    MonitorLog.status == "running",
                )
                .order_by(MonitorLog.id.desc())
                .first()
            )
            if log:
                log.status = "failed"
                log.error_message = f"Hard timeout after {NEWS_JOB_TIMEOUT}s"
                log.finished_at = datetime.now(timezone.utc)
                _safe_commit(db, "news_check: timeout update")
        except Exception as e:
            logger.error("Failed to update timeout log: %s", e)
        finally:
            db.close()
    except Exception as e:
        logger.error("News check unexpected error: %s", e)
        db = SessionLocal()
        try:
            log = (
                db.query(MonitorLog)
                .filter(
                    MonitorLog.job_name == "news_check",
                    MonitorLog.status == "running",
                )
                .order_by(MonitorLog.id.desc())
                .first()
            )
            if log:
                log.status = "failed"
                log.error_message = f"Unexpected error: {str(e)[:500]}"
                log.finished_at = datetime.now(timezone.utc)
                _safe_commit(db, "news_check: unexpected error update")
        except Exception:
            pass
        finally:
            db.close()


# ── Daily Summary Job ───────────────────────────────────────────────────

async def job_daily_summary():
    """Daily summary job."""
    logger.info("Running daily summary...")
    db = SessionLocal()
    notifier = create_notifier()

    try:
        today = datetime.now(timezone.utc).date()
        events = db.query(Event).filter(
            Event.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        ).all()

        event_dicts = [e.to_dict() for e in events]
        date_str = today.strftime("%d %B %Y")

        if notifier.enabled:
            await notifier.send_daily_summary(event_dicts, date_str)
            logger.info("Daily summary sent: %d events", len(event_dicts))

    except Exception as e:
        logger.error("Daily summary failed: %s", e)
    finally:
        db.close()


# ── Scheduler lifecycle ──────────────────────────────────────────────────

def start_scheduler():
    """Start the background scheduler."""
    bmkg_interval = settings.BMKG_CHECK_INTERVAL
    news_interval = settings.NEWS_CHECK_INTERVAL

    scheduler.add_job(
        job_check_bmkg,
        trigger=IntervalTrigger(seconds=bmkg_interval),
        id="bmkg_check",
        name="BMKG Earthquake Monitor",
        replace_existing=True,
    )

    scheduler.add_job(
        job_check_news,
        trigger=IntervalTrigger(seconds=news_interval),
        id="news_check",
        name="News RSS Monitor",
        replace_existing=True,
    )

    # Daily summary at 20:00 WIB (13:00 UTC)
    scheduler.add_job(
        job_daily_summary,
        trigger="cron",
        hour=13,
        minute=0,
        id="daily_summary",
        name="Daily Summary",
        replace_existing=True,
    )

    # Run watchdog once at startup to clean any stale logs from previous run
    cleanup_stale_logs()

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    logger.info("  - BMKG check: every %ds (hard timeout: %ds)", bmkg_interval, BMKG_JOB_TIMEOUT)
    logger.info("  - News check: every %ds (hard timeout: %ds)", news_interval, NEWS_JOB_TIMEOUT)
    logger.info("  - Daily summary: 20:00 WIB (hard timeout: %ds)", SUMMARY_JOB_TIMEOUT)


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
