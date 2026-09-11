"""
Risk Governance models — Stage 6 (docs/RAH_OS_Master_Plan.docx section 9).

`RiskConfig` is a singleton (one user, one account, per the master plan's
initial scope) — there is exactly one active row at a time. `KillSwitchEvent`
is append-only, per AGENTS.md section 4: the current state is always "the
most recent row," never an updated field, so the full history of state
changes is preserved for audit.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KillSwitchStateName(StrEnum):
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    SAFE_MODE = "SAFE_MODE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class RiskConfig(Base):
    """
    The user's risk settings. Singleton — always read/write the single most
    recently created row (see repository.py's get_or_create pattern, same
    approach as DataSource in Stage 2).

    Deliberately does NOT include max_daily_loss_pct or max_drawdown_pct
    yet: enforcing those honestly requires real trade P&L history, which
    doesn't exist until Stage 8/9. Storing a setting that nothing checks
    would be misleading — better to add it when it can actually be enforced.
    """

    __tablename__ = "risk_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_balance: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False, default=10000.0
    )
    max_risk_per_trade_pct: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, default=1.0
    )
    max_portfolio_heat_pct: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, default=5.0
    )
    max_open_positions: Mapped[int] = mapped_column(nullable=False, default=5)
    max_single_asset_exposure_pct: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, default=25.0
    )
    min_quality_grade: Mapped[str] = mapped_column(String(1), nullable=False, default="C")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class KillSwitchEvent(Base):
    __tablename__ = "kill_switch_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
