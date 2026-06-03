"""Initialize database and create/update default superadmin."""
import os
from pathlib import Path
from backend.core.database import init_db, SessionLocal
from backend.core.security import get_password_hash
from backend.core.config import get_settings
from backend.models.user import User


def seed_admin():
    """Create or update superadmin based on .env settings."""
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()

        if existing:
            # Update role ke superadmin jika belum
            changed = False
            if existing.role != "superadmin":
                existing.role = "superadmin"
                changed = True
            if not existing.email and settings.ADMIN_EMAIL:
                existing.email = settings.ADMIN_EMAIL
                changed = True
            if changed:
                db.commit()
                print(f"[OK] User '{settings.ADMIN_USERNAME}' di-update ke superadmin")
            else:
                print(f"[INFO] User '{settings.ADMIN_USERNAME}' sudah ada, skip.")
        else:
            # Cek apakah ada user lama dengan role superadmin (dari default sebelumnya)
            old_admin = db.query(User).filter(User.role == "superadmin").first()
            if old_admin:
                # Rename user lama jika username berubah
                if old_admin.username != settings.ADMIN_USERNAME:
                    old_admin.username = settings.ADMIN_USERNAME
                    old_admin.hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
                    old_admin.email = settings.ADMIN_EMAIL or old_admin.email
                    db.commit()
                    print(f"[OK] User '{old_admin.username}' di-rename ke '{settings.ADMIN_USERNAME}' & password di-update")
                else:
                    # Username sama, update password saja
                    old_admin.hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
                    db.commit()
                    print(f"[OK] Password user '{settings.ADMIN_USERNAME}' di-update dari .env")
            else:
                # Belum ada superadmin sama sekali, buat baru
                admin = User(
                    username=settings.ADMIN_USERNAME,
                    hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                    full_name="Superadmin",
                    role="superadmin",
                    email=settings.ADMIN_EMAIL or "admin@balmon-lampung.go.id",
                )
                db.add(admin)
                db.commit()
                print(f"[OK] Superadmin '{settings.ADMIN_USERNAME}' berhasil dibuat")
    finally:
        db.close()


if __name__ == "__main__":
    print("--- Initializing database...")

    # Buat folder data/ jika belum ada
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    init_db()
    print("[OK] Database tables created")
    print("--- Creating/updating superadmin...")
    seed_admin()
    print("[OK] Initialization complete!")
