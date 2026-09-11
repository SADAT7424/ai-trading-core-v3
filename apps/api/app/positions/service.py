"""
Position Management — service layer. Opens a Position from a filled Order
(Stage 7), and monitors open positions against FRESH market/macro data —
re-running the same engines used at entry (Stage 3/4), not stale numbers.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.go_os.macro.service import compute_macro_regime_snapshot
from app.market_core.service import compute_market_state
from app.models.execution import Order
from app.models.position import Position, PositionStatus
from app.positions.calculations import (
    ExitDecision,
    ThesisHealth,
    compute_target_price,
    compute_thesis_health,
    compute_trailing_stop,
    decide_exit,
)
from app.positions.repository import close_position, update_trailing_stop
from app.trading_core.calculations import Direction

# Only daily bars are ingested in this build (see market_core/service.py) —
# positions are monitored against the same interval they were opened on.
MONITORING_INTERVAL = "1day"


def open_position_from_order(db: Session, order: Order) -> Position:
    """
    Called immediately after an Order fills (see execution/service.py).
    Captures the entry thesis once, permanently — see app/models/position.py
    docstring on why these fields are never touched again.
    """
    direction = Direction(order.direction)
    assert order.filled_price is not None  # guaranteed: only called after a real fill
    entry_price = float(order.filled_price)
    stop_price = float(order.stop_price)
    target_price = compute_target_price(entry_price, stop_price, direction)

    thesis = (
        f"Opened as {order.classification or 'UNCLASSIFIED'} "
        f"(quality {order.quality_grade or '?'}), macro score "
        f"{order.entry_gold_macro_score if order.entry_gold_macro_score is not None else 'n/a'} "
        f"at entry. Target set at 2R (${target_price:.2f})."
    )

    position = Position(
        order_id=order.id,
        symbol=order.symbol,
        direction=order.direction,
        status=PositionStatus.OPEN,
        entry_price=entry_price,
        initial_stop_price=stop_price,
        current_stop_price=stop_price,
        target_price=target_price,
        units=float(order.units),
        risk_pct=float(order.risk_pct),
        entry_classification=order.classification,
        entry_quality_grade=order.quality_grade,
        entry_gold_macro_score=order.entry_gold_macro_score,
        entry_thesis=thesis,
    )
    db.add(position)
    db.commit()
    db.refresh(position)
    return position


@dataclass
class PositionMonitorResult:
    position: Position
    current_price: float
    thesis_health: ThesisHealth
    decision: ExitDecision


def monitor_position(db: Session, position: Position) -> PositionMonitorResult:
    direction = Direction(position.direction)

    market_state = compute_market_state(db, position.symbol, MONITORING_INTERVAL)
    macro_snapshot = compute_macro_regime_snapshot(db)
    current_gold_macro_score = macro_snapshot.gold_score.total

    # Trailing stop: tightened BEFORE the exit check, so a stop that just
    # trailed into being hit this bar is correctly treated as a stop-out,
    # not missed until the next monitoring cycle.
    new_stop = compute_trailing_stop(
        direction=direction,
        entry_price=float(position.entry_price),
        initial_stop_price=float(position.initial_stop_price),
        current_stop_price=float(position.current_stop_price),
        current_price=market_state.latest_close,
        atr=market_state.atr,
    )
    if new_stop != float(position.current_stop_price):
        position = update_trailing_stop(db, position, new_stop)

    thesis_health = compute_thesis_health(
        direction=direction,
        current_trend=market_state.trend,
        entry_gold_macro_score=position.entry_gold_macro_score or 0,
        current_gold_macro_score=current_gold_macro_score,
    )

    decision = decide_exit(
        direction=direction,
        current_price=market_state.latest_close,
        stop_price=float(position.current_stop_price),
        target_price=float(position.target_price),
        thesis_status=thesis_health.status,
    )

    if decision.action.value == "EXIT" and position.status == PositionStatus.OPEN:
        position = close_position(
            db, position, close_price=market_state.latest_close, reason=decision.reason.value
        )

    return PositionMonitorResult(
        position=position,
        current_price=market_state.latest_close,
        thesis_health=thesis_health,
        decision=decision,
    )


def monitor_all_open_positions(db: Session) -> list[PositionMonitorResult]:
    from app.positions.repository import get_open_positions

    return [monitor_position(db, p) for p in get_open_positions(db)]
