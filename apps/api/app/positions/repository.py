"""
Database access for Position Management. Kept separate from calculations.py
so the exit/health logic stays pure and DB-free (see that module's
docstring).
"""
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.position import Position, PositionStatus


def get_open_positions(db: Session, symbol: str | None = None) -> list[Position]:
    query = select(Position).where(Position.status == PositionStatus.OPEN)
    if symbol is not None:
        query = query.where(Position.symbol == symbol)
    return list(db.execute(query.order_by(Position.opened_at.desc())).scalars().all())


def get_portfolio_state(db: Session) -> tuple[int, float]:
    """
    The REAL current portfolio state, computed from actual open positions —
    not assumed. Returns (open_positions_count, total_open_risk_pct).

    This replaces the earlier (Stage 6) placeholder where callers had to
    manually supply these numbers, which meant the risk engine had no way
    to see positions that genuinely existed once Stage 8 started tracking
    them — a real correctness gap, not just a simplification.
    """
    open_positions = get_open_positions(db)
    total_risk_pct = sum(float(p.risk_pct) for p in open_positions)
    return len(open_positions), round(total_risk_pct, 4)


def get_today_realized_pnl(db: Session) -> float:
    """Sum of realized P&L for positions closed today (UTC), in dollars."""
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
    result = db.execute(
        select(func.sum(Position.realized_pnl)).where(
            Position.status == PositionStatus.CLOSED,
            Position.closed_at >= today_start,
        )
    ).scalar_one_or_none()
    return float(result) if result is not None else 0.0


def get_position(db: Session, position_id: str) -> Position | None:
    return db.get(Position, position_id)


def update_trailing_stop(db: Session, position: Position, new_stop_price: float) -> Position:
    """
    Updates ONLY current_stop_price — everything else about the position
    (especially the entry thesis fields) stays untouched. See
    app/models/position.py docstring on why entry fields never change.
    """
    position.current_stop_price = new_stop_price
    db.commit()
    db.refresh(position)
    return position


def close_position(
    db: Session, position: Position, close_price: float, reason: str
) -> Position:
    direction_sign = 1 if position.direction == "LONG" else -1
    realized_pnl = (
        (close_price - float(position.entry_price)) * float(position.units) * direction_sign
    )

    position.status = PositionStatus.CLOSED
    position.close_price = close_price
    position.close_reason = reason
    position.realized_pnl = round(realized_pnl, 2)
    position.closed_at = datetime.now(UTC)

    db.commit()
    db.refresh(position)
    return position
