"""Alert and notification tracking model."""
from backend.core.tz import WIB
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from backend.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    channel = Column(String(50), nullable=False)  # telegram, email, dashboard
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=lambda: datetime.now(WIB))
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "channel": self.channel,
            "message": self.message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "success": self.success,
        }


class MonitorLog(Base):
    """Log of monitoring job runs."""
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(WIB))
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running, success, failed
    events_found = Column(Integer, default=0)
    alerts_sent = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "job_name": self.job_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "events_found": self.events_found,
            "alerts_sent": self.alerts_sent,
        }
