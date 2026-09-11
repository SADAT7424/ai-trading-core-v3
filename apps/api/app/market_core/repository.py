"""
Database access for Market Core. Kept separate from calculations.py so the
indicator math stays pure and DB-free (see that module's docstring).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_core.calculations import Bar
from app.models.market import MarketBar


class NoMarketDataError(Exception):
    def __init__(self, symbol: str, interval: str) -> None:
        self.symbol = symbol
        self.interval = interval
        super().__init__(
            f"No bars for {symbol} @ {interval} yet. "
            f"POST /api/v1/market/bars/{symbol}/{interval}/ingest first."
        )


def get_recent_bars(
    db: Session, symbol: str, interval: str, limit: int = 200
) -> list[MarketBar]:
    """Most recent `limit` bars, returned in chronological (oldest-first) order."""
    rows = (
        db.execute(
            select(MarketBar)
            .where(MarketBar.symbol == symbol, MarketBar.interval == interval)
            .order_by(MarketBar.bar_time.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(reversed(rows))


def to_calculation_bars(rows: list[MarketBar]) -> list[Bar]:
    return [
        Bar(open=float(r.open), high=float(r.high), low=float(r.low), close=float(r.close))
        for r in rows
    ]
