"""
Market data models — Stage 4 (Market Core), the `market_bars` table from the
master plan's database section (docs/RAH_OS_Master_Plan.docx, 14.1).

Unlike economic observations, price bars are not meaningfully "revised" once
formed — no point-in-time vintage complexity is needed here. A simple
uniqueness constraint on (symbol, interval, bar_time) is enough to make
repeated ingestion runs idempotent.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketBar(Base):
    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "interval", "bar_time", name="uq_market_bar"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Canonical symbol format used throughout this system, e.g. "XAUUSD"
    # (no slash) — provider adapters translate to/from their own formats.
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    open: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
