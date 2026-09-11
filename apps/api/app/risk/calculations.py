"""
Risk Governance — pure calculations (Stage 6 in the master plan,
docs/RAH_OS_Master_Plan.docx section 9). Same discipline as every other
engine so far: pure functions, no database, no AI, fully deterministic.

This is the layer with absolute veto power (AGENTS.md's central rule): a
setup that looks excellent from Trading Core can still be rejected here.
Nothing here reduces or removes a limit automatically — it only ever
tightens (reduces position size) or blocks, never loosens.
"""
from dataclasses import dataclass, field
from enum import StrEnum

from app.models.risk import KillSwitchStateName
from app.trading_core.calculations import QualityGrade

_QUALITY_RANK = {QualityGrade.D: 1, QualityGrade.C: 2, QualityGrade.B: 3, QualityGrade.A: 4}


class RejectionReason(StrEnum):
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    QUALITY_BELOW_MINIMUM = "QUALITY_BELOW_MINIMUM"
    MAX_OPEN_POSITIONS_REACHED = "MAX_OPEN_POSITIONS_REACHED"
    MAX_PORTFOLIO_HEAT_EXCEEDED = "MAX_PORTFOLIO_HEAT_EXCEEDED"
    INVALID_STOP_DISTANCE = "INVALID_STOP_DISTANCE"


@dataclass
class RiskConfigInput:
    account_balance: float
    max_risk_per_trade_pct: float
    max_portfolio_heat_pct: float
    max_open_positions: int
    max_single_asset_exposure_pct: float
    min_quality_grade: QualityGrade


@dataclass
class PositionSize:
    risk_pct: float  # the ACTUAL risk %, after any automatic reduction
    risk_amount: float  # dollars
    units: float  # e.g. ounces of gold
    exposure_pct: float  # position value as % of account balance


def calculate_position_size(
    account_balance: float, risk_pct: float, entry_price: float, stop_price: float
) -> PositionSize:
    stop_distance = abs(entry_price - stop_price)
    if stop_distance == 0 or entry_price == 0:
        return PositionSize(risk_pct=0.0, risk_amount=0.0, units=0.0, exposure_pct=0.0)

    risk_amount = account_balance * (risk_pct / 100)
    units = risk_amount / stop_distance
    exposure_pct = (units * entry_price / account_balance) * 100 if account_balance else 0.0

    return PositionSize(
        risk_pct=round(risk_pct, 4),
        risk_amount=round(risk_amount, 2),
        units=round(units, 6),
        exposure_pct=round(exposure_pct, 3),
    )


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[RejectionReason] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # informational, e.g. "risk reduced from X to Y"
    position: PositionSize | None = None


def evaluate_trade(
    config: RiskConfigInput,
    kill_switch_state: KillSwitchStateName,
    quality: QualityGrade,
    proposed_risk_pct: float,
    entry_price: float,
    stop_price: float,
    open_positions_count: int,
    open_portfolio_heat_pct: float,
) -> RiskDecision:
    """
    The single entry point every proposed trade must pass through. Order of
    checks follows the master plan's risk hierarchy (section 9.3): account
    safety (kill switch) first, then hard structural limits, with position
    sizing/exposure as the last, adjustable step.
    """
    reasons: list[RejectionReason] = []
    notes: list[str] = []

    # 1. Account safety — absolute veto, checked first, nothing below matters if this fails.
    if kill_switch_state in (KillSwitchStateName.SAFE_MODE, KillSwitchStateName.EMERGENCY_STOP):
        return RiskDecision(
            approved=False,
            reasons=[RejectionReason.KILL_SWITCH_ACTIVE],
            notes=[f"Kill switch is {kill_switch_state.value} — no new risk permitted."],
        )
    if kill_switch_state is KillSwitchStateName.ALERT:
        notes.append("Kill switch is ALERT — proceeding, but under heightened caution.")

    # 2. Setup quality floor — a hard structural limit, not adjustable.
    if _QUALITY_RANK[quality] < _QUALITY_RANK[config.min_quality_grade]:
        reasons.append(RejectionReason.QUALITY_BELOW_MINIMUM)

    # 3. Open position count — a hard limit; you can't "partially" open a position.
    if open_positions_count + 1 > config.max_open_positions:
        reasons.append(RejectionReason.MAX_OPEN_POSITIONS_REACHED)

    if stop_price == entry_price:
        reasons.append(RejectionReason.INVALID_STOP_DISTANCE)
        return RiskDecision(approved=False, reasons=reasons, notes=notes, position=None)

    # 4. Position sizing — adjustable. Reduce risk %, and if needed exposure,
    #    rather than rejecting outright, mirroring the master plan's example
    #    in section 9.1 ("position size has been reduced automatically").
    effective_risk_pct = proposed_risk_pct
    if effective_risk_pct > config.max_risk_per_trade_pct:
        notes.append(
            f"Requested risk {proposed_risk_pct:.2f}% exceeds the configured max "
            f"{config.max_risk_per_trade_pct:.2f}% per trade — reduced automatically."
        )
        effective_risk_pct = config.max_risk_per_trade_pct

    position = calculate_position_size(
        config.account_balance, effective_risk_pct, entry_price, stop_price
    )

    if position.exposure_pct > config.max_single_asset_exposure_pct:
        # Shrink the position to fit the exposure cap, then recompute the
        # actual risk % that results — it will end up below what was asked.
        max_units = (config.max_single_asset_exposure_pct / 100 * config.account_balance) / (
            entry_price or 1
        )
        stop_distance = abs(entry_price - stop_price)
        reduced_risk_amount = max_units * stop_distance
        reduced_risk_pct = (
            (reduced_risk_amount / config.account_balance) * 100 if config.account_balance else 0.0
        )
        notes.append(
            f"Position further reduced to stay within the "
            f"{config.max_single_asset_exposure_pct:.1f}% max single-asset exposure limit."
        )
        position = PositionSize(
            risk_pct=round(reduced_risk_pct, 4),
            risk_amount=round(reduced_risk_amount, 2),
            units=round(max_units, 6),
            exposure_pct=round(config.max_single_asset_exposure_pct, 3),
        )

    # 5. Portfolio heat — a hard limit on total risk-in-play, checked with
    #    the ACTUAL (possibly reduced) risk this position would add.
    if open_portfolio_heat_pct + position.risk_pct > config.max_portfolio_heat_pct:
        reasons.append(RejectionReason.MAX_PORTFOLIO_HEAT_EXCEEDED)

    return RiskDecision(
        approved=len(reasons) == 0,
        reasons=reasons,
        notes=notes,
        position=position if len(reasons) == 0 else None,
    )
