"""Events CRUD routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from pydantic import BaseModel
from typing import Optional

from backend.core.database import get_db
from backend.models import Event, EventCategory, EventSeverity, EventStatus
from backend.models.event import VerifiedStatus
from backend.routes.auth import get_current_user, require_role
from backend.models.user import User

router = APIRouter(prefix="/api/events", tags=["events"])


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str = "lainnya"
    severity: str = "medium"
    kabupaten: Optional[str] = None
    kecamatan: Optional[str] = None
    kelurahan: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = "Manual"
    source_url: Optional[str] = None
    occurred_at: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    kabupaten: Optional[str] = None
    kecamatan: Optional[str] = None
    kelurahan: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    resolved_at: Optional[str] = None


@router.get("")
async def list_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    kabupaten: Optional[str] = None,
    kecamatan: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List events with filters."""
    query = db.query(Event)

    if category:
        query = query.filter(Event.category == category)
    if severity:
        query = query.filter(Event.severity == severity)
    if status:
        query = query.filter(Event.status == status)
    if kabupaten:
        query = query.filter(Event.kabupaten == kabupaten)
    if kecamatan:
        query = query.filter(Event.kecamatan == kecamatan)
    if source:
        query = query.filter(Event.source.ilike(f"%{source}%"))
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            query = query.filter(Event.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query = query.filter(Event.created_at <= dt)
        except ValueError:
            pass
    if search:
        query = query.filter(
            or_(
                Event.title.ilike(f"%{search}%"),
                Event.description.ilike(f"%{search}%"),
                Event.kabupaten.ilike(f"%{search}%"),
                Event.kecamatan.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    events = query.order_by(desc(Event.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "events": [e.to_dict() for e in events],
    }


@router.post("")
async def create_event(
    req: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "superadmin")),
):
    """Create a new event (operator+ only)."""
    occurred_at = None
    if req.occurred_at:
        try:
            occurred_at = datetime.fromisoformat(req.occurred_at)
        except ValueError:
            pass

    event = Event(
        title=req.title,
        description=req.description,
        category=req.category,
        severity=req.severity,
        kabupaten=req.kabupaten,
        kecamatan=req.kecamatan,
        kelurahan=req.kelurahan,
        latitude=req.latitude,
        longitude=req.longitude,
        source=req.source,
        source_url=req.source_url,
        occurred_at=occurred_at,
        created_by=current_user.id,
        province="Lampung",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.to_dict()


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get event by ID."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")
    return event.to_dict()


@router.put("/{event_id}")
async def update_event(
    event_id: int,
    req: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "superadmin")),
):
    """Update an event (operator+ only)."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")

    for field, value in req.model_dump(exclude_unset=True).items():
        if field == "resolved_at" and value:
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                value = None
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event.to_dict()


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("superadmin")),
):
    """Delete an event (superadmin only)."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")
    db.delete(event)
    db.commit()
    return {"message": "Event berhasil dihapus"}


class VerifyRequest(BaseModel):
    verified_status: str  # confirmed atau rejected
    verifier_notes: Optional[str] = None


@router.post("/{event_id}/verify")
async def verify_event(
    event_id: int,
    req: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "superadmin")),
):
    """Verifikasi event — apakah benar gangguan telekom (operator+)."""
    if req.verified_status not in ("confirmed", "rejected"):
        raise HTTPException(status_code=400, detail="verified_status harus 'confirmed' atau 'rejected'")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event tidak ditemukan")

    event.verified_status = req.verified_status
    event.verified_by = current_user.id
    event.verified_at = datetime.now(timezone.utc)
    event.verifier_notes = req.verifier_notes
    db.commit()
    db.refresh(event)
    return event.to_dict()


@router.get("/verify/pending")
async def list_pending_verification(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List event yang belum diverifikasi."""
    query = db.query(Event).filter(Event.verified_status == "pending")
    total = query.count()
    events = query.order_by(desc(Event.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "events": [e.to_dict() for e in events],
    }
