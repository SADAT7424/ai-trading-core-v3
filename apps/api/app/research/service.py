"""
Research/Backtesting — service layer. Ties the repository (real data) to
the backtest engine and statistics (pure logic) together.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.research.backtest import BacktestTrade, run_backtest
from app.research.repository import get_economic_points, get_price_bars
from app.research.statistics import BacktestStatistics, compute_backtest_statistics

REQUIRED_MACRO_SERIES = ["CPIAUCSL", "FEDFUNDS", "DFII10", "DTWEXBGS"]


class InsufficientBacktestDataError(Exception):
    def __init__(self, symbol: str, interval: str, bars_available: int, bars_required: int) -> None:
        self.symbol = symbol
        super().__init__(
            f"Only {bars_available} bars available for {symbol} @ {interval}; "
            f"need at least {bars_required} to run a backtest. Ingest more history first."
        )


@dataclass
class BacktestReport:
    symbol: str
    interval: str
    bars_used: int
    days_skipped_no_macro_data: int
    trades: list[BacktestTrade]
    statistics: BacktestStatistics


def run_backtest_for_symbol(db: Session, symbol: str, interval: str = "1day") -> BacktestReport:
    from app.research.backtest import MIN_BARS_REQUIRED

    bars = get_price_bars(db, symbol, interval)
    if len(bars) < MIN_BARS_REQUIRED:
        raise InsufficientBacktestDataError(symbol, interval, len(bars), MIN_BARS_REQUIRED)

    economic_series = get_economic_points(db, REQUIRED_MACRO_SERIES)

    result = run_backtest(bars, economic_series)
    statistics = compute_backtest_statistics(result.trades)

    return BacktestReport(
        symbol=symbol,
        interval=interval,
        bars_used=len(bars),
        days_skipped_no_macro_data=result.days_skipped_no_macro_data,
        trades=result.trades,
        statistics=statistics,
    )
