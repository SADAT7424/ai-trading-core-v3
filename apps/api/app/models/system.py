"""
Foundation-stage models.

This intentionally implements only the `system_events` audit table from the
master plan's database section — enough to prove migrations, the ORM, and the
audit-trail pattern work end-to-end. Domain tables (economic_events,
positions, orders, etc.) are added in their respective build stages.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemEvent(Base):
    """
    A generic, append-only audit record. Per AGENTS.md section 4, records like
    this are never updated or deleted — only inserted.
    """

    __tablename__ = "system_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
