"""
Database access for the Memory module (Stage 10,
docs/RAH_OS_Master_Plan.docx section 13). Reads existing Position data —
no new tables. Scope note: this is deliberately NOT a knowledge graph or a
general-purpose memory store — see app/memory/calculations.py docstring for
why that would be premature infrastructure right now.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position import Position, PositionStatus


@dataclass
class ClosedTradeRecord:
    classification: str | None
    quality_grade: str | None
    entry_gold_macro_score: int | None
    realized_pnl: float
    r_multiple: float | None  # None if risk distance was zero (shouldn't happen, but be safe)


def get_closed_trade_records(db: Session, symbol: str | None = None) -> list[ClosedTradeRecord]:
    query = select(Position).where(Position.status == PositionStatus.CLOSED)
    if symbol is not None:
        query = query.where(Position.symbol == symbol)
    rows = db.execute(query).scalars().all()

    records = []
    for row in rows:
        if row.realized_pnl is None:
            continue
        risk_distance = abs(float(row.entry_price) - float(row.initial_stop_price))
        risk_amount = risk_distance * float(row.units)
        r_multiple = (float(row.realized_pnl) / risk_amount) if risk_amount > 0 else None
        records.append(
            ClosedTradeRecord(
                classification=row.entry_classification,
                quality_grade=row.entry_quality_grade,
                entry_gold_macro_score=row.entry_gold_macro_score,
                realized_pnl=float(row.realized_pnl),
                r_multiple=r_multiple,
            )
        )
    return records
