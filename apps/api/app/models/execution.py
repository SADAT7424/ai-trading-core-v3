"""
Execution models — Stage 7 (docs/RAH_OS_Master_Plan.docx section 10).

`Order` is append-only in spirit, per AGENTS.md section 4: once an order
reaches a terminal state (FILLED, REJECTED, CANCELLED), nothing about it
changes. The lifecycle only ever moves forward through `OrderStatus`.

IMPORTANT: `broker` is always "PAPER" in this build. There is no real broker
adapter, no real broker credentials anywhere in this codebase, and no path
to real-money execution — per AGENTS.md section 0/7 and the master plan's
staged deployment requirement (section 4.10): Backtest -> Paper -> Shadow ->
Controlled Live -> Production, never skipping a stage. This model exists to
prove the execution pipeline (risk-approved opportunity -> order ->
simulated fill) end to end, safely.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderStatus(StrEnum):
    REJECTED = "REJECTED"  # failed risk evaluation — never sent anywhere
    FILLED = "FILLED"  # paper fill completed
    CANCELLED = "CANCELLED"  # reserved for future use (e.g. manual cancel before fill)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # LONG | SHORT
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Broker is always "PAPER" — see module docstring.
    broker: Mapped[str] = mapped_column(String(20), nullable=False, default="PAPER")

    requested_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    filled_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    stop_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    units: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)

    risk_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    risk_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)

    quality_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rejection_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
