"""Application configuration from environment variables."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Lampung Infrastructure Monitor"
    APP_PORT: int = 8032
    APP_HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite:///data/lampung_monitor.db"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Monitoring intervals (seconds)
    BMKG_CHECK_INTERVAL: int = 300       # 5 minutes
    NEWS_CHECK_INTERVAL: int = 3600      # 1 hour
    DISASTER_CHECK_INTERVAL: int = 7200  # 2 hours

    # Lampung bounding box
    LAMPUNG_LAT_MIN: float = -6.5
    LAMPUNG_LAT_MAX: float = -3.5
    LAMPUNG_LON_MIN: float = 103.5
    LAMPUNG_LON_MAX: float = 106.0

    # Default admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_EMAIL: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def database_path(self) -> Path:
        """Extract SQLite path from DATABASE_URL."""
        db_path = self.DATABASE_URL.replace("sqlite:///", "")
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
