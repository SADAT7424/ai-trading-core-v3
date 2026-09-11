"""
Risk Governance — service layer. Takes a Stage 5 opportunity, derives a
stop-loss from real ATR (Stage 4), and runs it through the deterministic
risk rules (calculations.py) using the person's actual configured limits.

Portfolio state (open positions count, current heat, today's realized P&L)
is now computed from REAL Stage 8 position data — this used to be accepted
as caller-supplied parameters defaulting to "assume a flat account," which
was accurate only when no position tracking existed yet. Once positions
were real, that default became a genuine correctness gap: the risk engine
could approve trades that would breach limits it just couldn't see. Fixed
by querying the real state here instead of trusting a caller's guess.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.market_core.service import compute_market_state
from app.models.risk import KillSwitchStateName
from app.positions.repository import get_portfolio_state, get_today_realized_pnl
from app.risk.calculations import RiskConfigInput, RiskDecision, evaluate_trade
from app.risk.repository import get_current_kill_switch_state, get_or_create_risk_config
from app.trading_core.calculations import Direction, QualityGrade
from app.trading_core.service import compute_opportunity

DEFAULT_ATR_STOP_MULTIPLIER = 1.5


@dataclass
class TradeEvaluation:
    symbol: str
    direction: Direction
    entry_price: float
    stop_price: float | None
    quality: QualityGrade | None
    classification: str | None
    gold_macro_score: int
    kill_switch_state: KillSwitchStateName
    decision: RiskDecision


def evaluate_trade_for_symbol(
    db: Session,
    symbol: str,
    interval: str = "1day",
    atr_multiplier: float = DEFAULT_ATR_STOP_MULTIPLIER,
    proposed_risk_pct: float | None = None,
) -> TradeEvaluation:
    opportunity = compute_opportunity(db, symbol, interval)
    market_state = compute_market_state(db, symbol, interval)
    config_row = get_or_create_risk_config(db)
    kill_switch_state = get_current_kill_switch_state(db)

    open_positions_count, open_portfolio_heat_pct = get_portfolio_state(db)
    today_realized_pnl = get_today_realized_pnl(db)

    config = RiskConfigInput(
        account_balance=float(config_row.account_balance),
        max_risk_per_trade_pct=float(config_row.max_risk_per_trade_pct),
        max_portfolio_heat_pct=float(config_row.max_portfolio_heat_pct),
        max_open_positions=config_row.max_open_positions,
        max_single_asset_exposure_pct=float(config_row.max_single_asset_exposure_pct),
        max_daily_loss_pct=float(config_row.max_daily_loss_pct),
        min_quality_grade=QualityGrade(config_row.min_quality_grade),
    )

    if opportunity.setup.direction is Direction.NONE or opportunity.score is None:
        return TradeEvaluation(
            symbol=symbol,
            direction=Direction.NONE,
            entry_price=opportunity.latest_close,
            stop_price=None,
            quality=None,
            classification=opportunity.classification.value,
            gold_macro_score=opportunity.gold_macro_score,
            kill_switch_state=kill_switch_state,
            decision=RiskDecision(approved=False, reasons=[], notes=["No setup to evaluate."]),
        )

    entry_price = opportunity.latest_close
    atr_distance = market_state.atr * atr_multiplier
    stop_price = (
        entry_price - atr_distance
        if opportunity.setup.direction is Direction.LONG
        else entry_price + atr_distance
    )

    risk_pct = (
        proposed_risk_pct if proposed_risk_pct is not None else config.max_risk_per_trade_pct
    )

    decision = evaluate_trade(
        config=config,
        kill_switch_state=kill_switch_state,
        quality=opportunity.score.quality,
        proposed_risk_pct=risk_pct,
        entry_price=entry_price,
        stop_price=stop_price,
        open_positions_count=open_positions_count,
        open_portfolio_heat_pct=open_portfolio_heat_pct,
        today_realized_pnl=today_realized_pnl,
    )

    return TradeEvaluation(
        symbol=symbol,
        direction=opportunity.setup.direction,
        entry_price=entry_price,
        stop_price=round(stop_price, 4),
        quality=opportunity.score.quality,
        classification=opportunity.classification.value,
        gold_macro_score=opportunity.gold_macro_score,
        kill_switch_state=kill_switch_state,
        decision=decision,
    )
