"""Background scheduler for monitoring jobs."""
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


async def job_check_bmkg():
    """BMKG monitoring job."""
    logger.info("Running BMKG check...")
    db = SessionLocal()
    notifier = create_notifier()
    log = MonitorLog(job_name="bmkg_check", started_at=datetime.now(timezone.utc))
    db.add(log)
    db.commit()

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
        db.commit()
        logger.info(f"BMKG check done: {events_found} events found, {alerts_sent} alerts sent")

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"BMKG check failed: {e}")
    finally:
        db.close()


async def job_check_news():
    """News monitoring job."""
    logger.info("Running news check...")
    db = SessionLocal()
    notifier = create_notifier()
    log = MonitorLog(job_name="news_check", started_at=datetime.now(timezone.utc))
    db.add(log)
    db.commit()

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
        db.commit()
        logger.info(f"News check done: {events_found} events found, {alerts_sent} alerts sent")

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.error(f"News check failed: {e}")
    finally:
        db.close()


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
            logger.info(f"Daily summary sent: {len(event_dicts)} events")

    except Exception as e:
        logger.error(f"Daily summary failed: {e}")
    finally:
        db.close()


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

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    logger.info(f"  - BMKG check: every {bmkg_interval}s")
    logger.info(f"  - News check: every {news_interval}s")
    logger.info(f"  - Daily summary: 20:00 WIB")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
