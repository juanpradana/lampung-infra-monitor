"""Initialize database and create default superadmin."""
from backend.core.database import init_db, SessionLocal
from backend.core.security import get_password_hash
from backend.core.config import get_settings
from backend.models.user import User


def seed_admin():
    """Create default superadmin if not exists."""
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if existing:
            print(f"User '{settings.ADMIN_USERNAME}' sudah ada, skip.")
            return

        admin = User(
            username=settings.ADMIN_USERNAME,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            full_name="Superadmin",
            role="superadmin",
            email="admin@balmon-lampung.go.id",
        )
        db.add(admin)
        db.commit()
        print(f"✅ Superadmin '{settings.ADMIN_USERNAME}' berhasil dibuat")
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Initializing database...")
    init_db()
    print("✅ Database tables created")
    print("🔧 Creating default superadmin...")
    seed_admin()
    print("✅ Initialization complete!")
