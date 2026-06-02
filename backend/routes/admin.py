"""Admin routes - user management and system operations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.core.database import get_db
from backend.core.security import get_password_hash
from backend.models.user import User
from backend.models.event import LAMPUNG_LOCATIONS
from backend.routes.auth import require_role
from backend.services.telegram_bot import create_notifier
from backend.services.scheduler import job_check_bmkg, job_check_news, job_daily_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class TelegramTest(BaseModel):
    message: str = "🔔 Test notifikasi dari Lampung Infrastructure Monitor"


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("superadmin")),
):
    """List all users (superadmin only)."""
    users = db.query(User).order_by(User.created_at).all()
    return {"users": [u.to_dict() for u in users]}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("superadmin")),
):
    """Update user (superadmin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    if req.role and req.role not in ("superadmin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Role tidak valid")

    if req.email is not None:
        user.email = req.email
    if req.full_name is not None:
        user.full_name = req.full_name
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.password:
        user.hashed_password = get_password_hash(req.password)

    db.commit()
    db.refresh(user)
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("superadmin")),
):
    """Delete user (superadmin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus diri sendiri")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    db.delete(user)
    db.commit()
    return {"message": f"User {user.username} berhasil dihapus"}


@router.get("/locations")
async def get_locations(
    current_user: User = Depends(require_role("superadmin", "operator", "viewer")),
):
    """Get Lampung location hierarchy."""
    return {"locations": LAMPUNG_LOCATIONS}


@router.post("/monitoring/trigger")
async def trigger_monitoring(
    job: str = "all",
    current_user: User = Depends(require_role("superadmin")),
):
    """Manually trigger monitoring jobs (superadmin only)."""
    results = {}
    if job in ("all", "bmkg"):
        await job_check_bmkg()
        results["bmkg"] = "triggered"
    if job in ("all", "news"):
        await job_check_news()
        results["news"] = "triggered"
    if job in ("all", "summary"):
        await job_daily_summary()
        results["summary"] = "triggered"
    return {"message": "Monitoring triggered", "jobs": results}


@router.post("/telegram/test")
async def test_telegram(
    req: TelegramTest,
    current_user: User = Depends(require_role("superadmin")),
):
    """Test Telegram notification (superadmin only)."""
    notifier = create_notifier()
    if not notifier.enabled:
        raise HTTPException(status_code=400, detail="Telegram belum dikonfigurasi")

    success = await notifier.send_message(req.message)
    if success:
        return {"message": "Pesan berhasil dikirim ke Telegram"}
    else:
        raise HTTPException(status_code=500, detail="Gagal mengirim pesan ke Telegram")
