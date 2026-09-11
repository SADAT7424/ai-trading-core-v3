"""
/api/v1/performance — trade performance summary, computed fresh from
existing closed positions on every request. No new tables.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.performance.calculations import compute_performance_summary
from app.performance.repository import get_closed_position_pnls

router = APIRouter(prefix="/performance", tags=["performance"])


class PerformanceSummaryResponse(BaseModel):
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_realized_pnl: float
    average_win: float
    average_loss: float
    profit_factor: float | None
    expectancy: float


@router.get("/summary", response_model=PerformanceSummaryResponse)
def get_performance_summary(
    symbol: str | None = None, db: Session = Depends(get_db)
) -> PerformanceSummaryResponse:
    pnls = get_closed_position_pnls(db, symbol)
    summary = compute_performance_summary(pnls)
    return PerformanceSummaryResponse(
        total_trades=summary.total_trades,
        wins=summary.wins,
        losses=summary.losses,
        win_rate_pct=summary.win_rate_pct,
        total_realized_pnl=summary.total_realized_pnl,
        average_win=summary.average_win,
        average_loss=summary.average_loss,
        profit_factor=summary.profit_factor,
        expectancy=summary.expectancy,
    )
