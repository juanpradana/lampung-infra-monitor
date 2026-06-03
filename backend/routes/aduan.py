"""Aduan/Complaint routes — CRUD & statistik aduan gangguan telekomunikasi."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional

from backend.core.database import get_db
from backend.models import Aduan, AduanStatus
from backend.routes.auth import get_current_user, require_role
from backend.models.user import User

router = APIRouter(prefix="/api/aduan", tags=["aduan"])


def generate_nomor(db: Session) -> str:
    """Generate nomor aduan: ADM-YYYYMM-XXXX"""
    now = datetime.now(timezone.utc)
    prefix = f"ADM-{now.strftime('%Y%m')}-"
    last = db.query(Aduan).filter(
        Aduan.nomor.like(f"{prefix}%")
    ).order_by(desc(Aduan.id)).first()
    if last and last.nomor:
        try:
            seq = int(last.nomor.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


class AduanCreate(BaseModel):
    judul: str
    deskripsi: Optional[str] = None
    pelapor_nama: str
    pelapor_telp: Optional[str] = None
    pelapor_email: Optional[str] = None
    kategori: str = "gangguan_lain"
    keparahan: str = "sedang"
    sumber: str = "masyarakat"
    lokasi_kabupaten: Optional[str] = None
    lokasi_kecamatan: Optional[str] = None
    lokasi_kelurahan: Optional[str] = None
    lokasi_detail: Optional[str] = None


class AduanUpdate(BaseModel):
    judul: Optional[str] = None
    deskripsi: Optional[str] = None
    kategori: Optional[str] = None
    keparahan: Optional[str] = None
    status: Optional[str] = None
    lokasi_kabupaten: Optional[str] = None
    lokasi_kecamatan: Optional[str] = None
    lokasi_kelurahan: Optional[str] = None
    lokasi_detail: Optional[str] = None
    penanganan: Optional[str] = None
    catatan_internal: Optional[str] = None
    event_id: Optional[int] = None


@router.get("")
async def list_aduan(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    kategori: Optional[str] = None,
    keparahan: Optional[str] = None,
    kabupaten: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List aduan dengan filter."""
    query = db.query(Aduan)

    if status:
        query = query.filter(Aduan.status == status)
    if kategori:
        query = query.filter(Aduan.kategori == kategori)
    if keparahan:
        query = query.filter(Aduan.keparahan == keparahan)
    if kabupaten:
        query = query.filter(Aduan.lokasi_kabupaten == kabupaten)
    if search:
        from sqlalchemy import or_
        query = query.filter(or_(
            Aduan.judul.ilike(f"%{search}%"),
            Aduan.deskripsi.ilike(f"%{search}%"),
            Aduan.pelapor_nama.ilike(f"%{search}%"),
            Aduan.nomor.ilike(f"%{search}%"),
        ))

    total = query.count()
    aduan_list = query.order_by(desc(Aduan.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "aduan": [a.to_dict() for a in aduan_list],
    }


@router.post("")
async def create_aduan(
    req: AduanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "superadmin")),
):
    """Buat aduan baru (operator+)."""
    aduan = Aduan(
        nomor=generate_nomor(db),
        judul=req.judul,
        deskripsi=req.deskripsi,
        pelapor_nama=req.pelapor_nama,
        pelapor_telp=req.pelapor_telp,
        pelapor_email=req.pelapor_email,
        kategori=req.kategori,
        keparahan=req.keparahan,
        sumber=req.sumber,
        lokasi_kabupaten=req.lokasi_kabupaten,
        lokasi_kecamatan=req.lokasi_kecamatan,
        lokasi_kelurahan=req.lokasi_kelurahan,
        lokasi_detail=req.lokasi_detail,
        created_by=current_user.id,
    )
    db.add(aduan)
    db.commit()
    db.refresh(aduan)
    return aduan.to_dict()


@router.get("/stats")
async def get_aduan_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Statistik aduan."""
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total = db.query(func.count(Aduan.id)).filter(Aduan.created_at >= since).scalar() or 0
    by_status = {}
    for s, c in db.query(Aduan.status, func.count(Aduan.id)).filter(
        Aduan.created_at >= since
    ).group_by(Aduan.status).all():
        by_status[s] = c

    by_kategori = {}
    for k, c in db.query(Aduan.kategori, func.count(Aduan.id)).filter(
        Aduan.created_at >= since
    ).group_by(Aduan.kategori).all():
        by_kategori[k] = c

    by_kabupaten = []
    for kab, c in db.query(Aduan.lokasi_kabupaten, func.count(Aduan.id)).filter(
        Aduan.created_at >= since, Aduan.lokasi_kabupaten.isnot(None)
    ).group_by(Aduan.lokasi_kabupaten).order_by(desc(func.count(Aduan.id))).limit(10).all():
        by_kabupaten.append({"kabupaten": kab, "count": c})

    resolved = db.query(func.count(Aduan.id)).filter(
        Aduan.created_at >= since, Aduan.status == "selesai"
    ).scalar() or 0

    return {
        "total": total,
        "resolved": resolved,
        "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
        "by_status": by_status,
        "by_kategori": by_kategori,
        "by_kabupaten": by_kabupaten,
    }


@router.get("/{aduan_id}")
async def get_aduan(
    aduan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detail aduan."""
    aduan = db.query(Aduan).filter(Aduan.id == aduan_id).first()
    if not aduan:
        raise HTTPException(status_code=404, detail="Aduan tidak ditemukan")
    return aduan.to_dict()


@router.put("/{aduan_id}")
async def update_aduan(
    aduan_id: int,
    req: AduanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "superadmin")),
):
    """Update aduan (operator+)."""
    aduan = db.query(Aduan).filter(Aduan.id == aduan_id).first()
    if not aduan:
        raise HTTPException(status_code=404, detail="Aduan tidak ditemukan")

    for field, value in req.model_dump(exclude_unset=True).items():
        if field == "status" and value == "selesai" and not aduan.resolved_at:
            aduan.resolved_at = datetime.now(timezone.utc)
        setattr(aduan, field, value)

    db.commit()
    db.refresh(aduan)
    return aduan.to_dict()


@router.delete("/{aduan_id}")
async def delete_aduan(
    aduan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("superadmin")),
):
    """Hapus aduan (superadmin only)."""
    aduan = db.query(Aduan).filter(Aduan.id == aduan_id).first()
    if not aduan:
        raise HTTPException(status_code=404, detail="Aduan tidak ditemukan")
    db.delete(aduan)
    db.commit()
    return {"message": "Aduan berhasil dihapus"}
