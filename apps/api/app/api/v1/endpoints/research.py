"""
/api/v1/research — backtesting. Runs entirely on data already ingested
(Stage 2 + Stage 4) — no new external calls, no cost, safe to run as often
as you like.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.research.backtest import TradeExitReason
from app.research.service import InsufficientBacktestDataError, run_backtest_for_symbol
from app.trading_core.calculations import Direction, TradeClassification

router = APIRouter(prefix="/research", tags=["research"])


class BacktestTradeResponse(BaseModel):
    direction: Direction
    classification: TradeClassification
    entry_date: date
    entry_price: float
    stop_price: float
    target_price: float
    exit_date: date
    exit_price: float
    exit_reason: TradeExitReason
    bars_held: int
    r_multiple: float


class BacktestStatisticsResponse(BaseModel):
    total_trades: int
    still_open_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_r: float
    average_r: float
    profit_factor: float | None
    max_drawdown_r: float
    equity_curve_r: list[float]


class BacktestReportResponse(BaseModel):
    symbol: str
    interval: str
    bars_used: int
    days_skipped_no_macro_data: int
    statistics: BacktestStatisticsResponse
    trades: list[BacktestTradeResponse]


@router.post("/backtest/{symbol}", response_model=BacktestReportResponse)
def run_backtest_endpoint(
    symbol: str, interval: str = "1day", db: Session = Depends(get_db)
) -> BacktestReportResponse:
    try:
        report = run_backtest_for_symbol(db, symbol, interval)
    except InsufficientBacktestDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestReportResponse(
        symbol=report.symbol,
        interval=report.interval,
        bars_used=report.bars_used,
        days_skipped_no_macro_data=report.days_skipped_no_macro_data,
        statistics=BacktestStatisticsResponse(
            total_trades=report.statistics.total_trades,
            still_open_trades=report.statistics.still_open_trades,
            wins=report.statistics.wins,
            losses=report.statistics.losses,
            win_rate_pct=report.statistics.win_rate_pct,
            total_r=report.statistics.total_r,
            average_r=report.statistics.average_r,
            profit_factor=report.statistics.profit_factor,
            max_drawdown_r=report.statistics.max_drawdown_r,
            equity_curve_r=report.statistics.equity_curve_r,
        ),
        trades=[
            BacktestTradeResponse(
                direction=t.direction,
                classification=t.classification,
                entry_date=t.entry_date,
                entry_price=t.entry_price,
                stop_price=t.stop_price,
                target_price=t.target_price,
                exit_date=t.exit_date,
                exit_price=t.exit_price,
                exit_reason=t.exit_reason,
                bars_held=t.bars_held,
                r_multiple=t.r_multiple,
            )
            for t in report.trades
        ],
    )
