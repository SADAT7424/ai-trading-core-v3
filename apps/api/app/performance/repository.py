"""
Database access for performance summaries. Reads existing Position data —
adds no new tables or columns.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position import Position, PositionStatus


def get_closed_position_pnls(db: Session, symbol: str | None = None) -> list[float]:
    query = select(Position.realized_pnl).where(Position.status == PositionStatus.CLOSED)
    if symbol is not None:
        query = query.where(Position.symbol == symbol)
    rows = db.execute(query).scalars().all()
    return [float(p) for p in rows if p is not None]
