"""
Position models — Stage 8 (docs/RAH_OS_Master_Plan.docx section 11).

A Position is opened automatically from a FILLED Order (Stage 7) and is
what gets actively monitored afterward. Per the master plan's "Trade Thesis
Object" (section 11.1) and AGENTS.md section 4: the entry thesis fields
(entry_price, initial_stop_price, target_price, entry_classification,
entry_quality_grade, entry_gold_macro_score) are captured once at open time
and NEVER modified — the system must always be able to answer "why did it
open this position," independent of anything that happens afterward.

Only `current_stop_price` (trailing, in later work) and the closing fields
are ever written after the position opens.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CloseReason(StrEnum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), unique=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # LONG | SHORT
    status: Mapped[str] = mapped_column(String(10), nullable=False, index=True, default="OPEN")

    # --- Entry thesis: immutable once written (see module docstring) ---
    entry_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    initial_stop_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    target_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    units: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    risk_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=0.0)
    entry_classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entry_quality_grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    entry_gold_macro_score: Mapped[int | None] = mapped_column(nullable=True)
    entry_thesis: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Mutable monitoring state ---
    current_stop_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)

    # --- Closing facts: written once, at close, then frozen ---
    close_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
