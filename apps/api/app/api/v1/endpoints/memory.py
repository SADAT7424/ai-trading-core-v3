"""
/api/v1/memory — trade history insights. Computed fresh from existing
closed positions on every request — no new tables.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.go_os.macro.repository import SeriesNotIngestedError
from app.go_os.macro.service import compute_macro_regime_snapshot
from app.memory.calculations import (
    breakdown_by_classification,
    breakdown_by_quality_grade,
    find_similar_historical_setups,
)
from app.memory.repository import get_closed_trade_records
from app.performance.calculations import PerformanceSummary
from app.trading_core.service import compute_opportunity

router = APIRouter(prefix="/memory", tags=["memory"])


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


class GroupedPerformanceResponse(BaseModel):
    group: str
    summary: PerformanceSummaryResponse


def _summary_response(summary: PerformanceSummary) -> PerformanceSummaryResponse:
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


@router.get("/insights", response_model=list[GroupedPerformanceResponse])
def get_insights_by_classification(
    symbol: str | None = None, db: Session = Depends(get_db)
) -> list[GroupedPerformanceResponse]:
    records = get_closed_trade_records(db, symbol)
    breakdown = breakdown_by_classification(records)
    return [
        GroupedPerformanceResponse(group=g.group, summary=_summary_response(g.summary))
        for g in breakdown
    ]


@router.get("/insights/by-grade", response_model=list[GroupedPerformanceResponse])
def get_insights_by_grade(
    symbol: str | None = None, db: Session = Depends(get_db)
) -> list[GroupedPerformanceResponse]:
    records = get_closed_trade_records(db, symbol)
    breakdown = breakdown_by_quality_grade(records)
    return [
        GroupedPerformanceResponse(group=g.group, summary=_summary_response(g.summary))
        for g in breakdown
    ]


class SimilarSetupsResponse(BaseModel):
    current_gold_macro_score: int
    similar_trade_count: int
    tolerance: int
    similar_trades_summary: PerformanceSummaryResponse


@router.get("/similar-setups/{symbol}", response_model=SimilarSetupsResponse)
def get_similar_setups(
    symbol: str, interval: str = "1day", db: Session = Depends(get_db)
) -> SimilarSetupsResponse:
    try:
        opportunity = compute_opportunity(db, symbol, interval)
        macro = compute_macro_regime_snapshot(db)
    except (SeriesNotIngestedError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    records = get_closed_trade_records(db, symbol)
    result = find_similar_historical_setups(
        records,
        current_gold_macro_score=macro.gold_score.total,
        current_classification=opportunity.classification.value,
    )
    return SimilarSetupsResponse(
        current_gold_macro_score=result.current_gold_macro_score,
        similar_trade_count=result.similar_trade_count,
        tolerance=result.tolerance,
        similar_trades_summary=_summary_response(result.similar_trades_summary),
    )
