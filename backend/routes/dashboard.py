"""Dashboard data routes - statistics and aggregations."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional

from backend.core.database import get_db
from backend.models import Event, MonitorLog
from backend.models.event import VerifiedStatus
from backend.routes.auth import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary statistics."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total = db.query(func.count(Event.id)).filter(Event.created_at >= since).scalar() or 0
    active = db.query(func.count(Event.id)).filter(Event.created_at >= since, Event.status == "active").scalar() or 0
    resolved = db.query(func.count(Event.id)).filter(Event.created_at >= since, Event.status == "resolved").scalar() or 0

    # Today
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.query(func.count(Event.id)).filter(Event.created_at >= today).scalar() or 0

    # By severity
    severity_counts = {}
    for sev, count in db.query(Event.severity, func.count(Event.id)).filter(Event.created_at >= since).group_by(Event.severity).all():
        severity_counts[sev] = count

    # By category
    category_counts = {}
    for cat, count in db.query(Event.category, func.count(Event.id)).filter(Event.created_at >= since).group_by(Event.category).all():
        category_counts[cat] = count

    # By verified status
    verified_counts = {}
    for vs, count in db.query(Event.verified_status, func.count(Event.id)).filter(Event.created_at >= since).group_by(Event.verified_status).all():
        verified_counts[vs] = count

    # Confirmed telecom incidents
    confirmed = db.query(func.count(Event.id)).filter(
        Event.created_at >= since, Event.verified_status == "confirmed"
    ).scalar() or 0

    # Top kabupaten
    top_kabupaten = []
    for kab, count in db.query(Event.kabupaten, func.count(Event.id)).filter(
        Event.created_at >= since, Event.kabupaten.isnot(None)
    ).group_by(Event.kabupaten).order_by(desc(func.count(Event.id))).limit(10).all():
        top_kabupaten.append({"kabupaten": kab, "count": count})

    return {
        "period_days": days,
        "total_events": total,
        "active_events": active,
        "resolved_events": resolved,
        "today_events": today_count,
        "confirmed_events": confirmed,
        "verified_counts": verified_counts,
        "by_severity": severity_counts,
        "by_category": category_counts,
        "top_kabupaten": top_kabupaten,
    }


@router.get("/timeline")
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    category: Optional[str] = None,
    kabupaten: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get timeline data for charts."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(Event).filter(Event.created_at >= since)

    if category:
        query = query.filter(Event.category == category)
    if kabupaten:
        query = query.filter(Event.kabupaten == kabupaten)

    events = query.order_by(Event.created_at).all()

    # Group by date
    timeline = {}
    for event in events:
        date_key = event.created_at.strftime("%Y-%m-%d") if event.created_at else "unknown"
        if date_key not in timeline:
            timeline[date_key] = {"date": date_key, "total": 0, "categories": {}}
        timeline[date_key]["total"] += 1
        cat = event.category or "lainnya"
        timeline[date_key]["categories"][cat] = timeline[date_key]["categories"].get(cat, 0) + 1

    return {"timeline": list(timeline.values())}


@router.get("/by-location")
async def get_by_location(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get events grouped by location (kabupaten/kota)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = []
    for kab, count in db.query(Event.kabupaten, func.count(Event.id)).filter(
        Event.created_at >= since, Event.kabupaten.isnot(None)
    ).group_by(Event.kabupaten).order_by(desc(func.count(Event.id))).all():
        # Get severity breakdown for each kabupaten
        sev_counts = {}
        for sev, cnt in db.query(Event.severity, func.count(Event.id)).filter(
            Event.created_at >= since, Event.kabupaten == kab
        ).group_by(Event.severity).all():
            sev_counts[sev] = cnt

        results.append({
            "kabupaten": kab,
            "total": count,
            "severity": sev_counts,
        })

    return {"locations": results}


@router.get("/by-category")
async def get_by_category(
    days: int = Query(30, ge=1, le=365),
    kabupaten: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get events grouped by category."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(Event).filter(Event.created_at >= since)

    if kabupaten:
        query = query.filter(Event.kabupaten == kabupaten)

    results = []
    for cat, count in query.with_entities(Event.category, func.count(Event.id)).group_by(Event.category).all():
        results.append({"category": cat, "count": count})

    return {"categories": results}


@router.get("/monitoring-logs")
async def get_monitoring_logs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent monitoring job logs."""
    logs = db.query(MonitorLog).order_by(desc(MonitorLog.started_at)).limit(limit).all()
    return {"logs": [l.to_dict() for l in logs]}
