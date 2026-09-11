"""
Market bar ingestion service — mirrors the structure of
app/data/ingestion/economic.py but simpler, since bars don't need
point-in-time vintage handling (see app/models/market.py docstring).
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.data.providers.market_base import MarketDataProvider
from app.models.market import MarketBar

log = get_logger(__name__)


@dataclass
class BarIngestSummary:
    symbol: str
    interval: str
    fetched: int
    inserted: int
    already_present: int


def _normalize_for_comparison(dt: datetime) -> datetime:
    """
    Some database backends (notably SQLite) don't round-trip timezone info
    on DateTime(timezone=True) columns — a value stored as UTC-aware can
    come back naive. Comparing tz-aware and naive datetimes for equality
    either raises or silently never matches, which would break the
    idempotency this function exists to guarantee. Normalizing both sides
    to naive UTC before comparing sidesteps this regardless of backend.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def ingest_bars(
    db: Session,
    provider: MarketDataProvider,
    symbol: str,
    interval: str,
    outputsize: int = 200,
) -> BarIngestSummary:
    bars = provider.fetch_bars(symbol, interval, outputsize=outputsize)

    existing_times = {
        _normalize_for_comparison(row[0])
        for row in db.execute(
            select(MarketBar.bar_time).where(
                MarketBar.symbol == symbol, MarketBar.interval == interval
            )
        ).all()
    }

    inserted = 0
    for bar in bars:
        key = _normalize_for_comparison(bar.bar_time)
        if key in existing_times:
            continue
        db.add(
            MarketBar(
                symbol=bar.symbol,
                interval=bar.interval,
                bar_time=bar.bar_time,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
        )
        existing_times.add(key)
        inserted += 1

    db.commit()

    summary = BarIngestSummary(
        symbol=symbol,
        interval=interval,
        fetched=len(bars),
        inserted=inserted,
        already_present=len(bars) - inserted,
    )
    log.info(
        "market_bars_ingested",
        symbol=symbol,
        interval=interval,
        fetched=summary.fetched,
        inserted=summary.inserted,
        already_present=summary.already_present,
    )
    return summary
