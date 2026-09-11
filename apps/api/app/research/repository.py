"""
Database access for backtesting — fetches REAL ingested history (Stage 2's
economic observations, Stage 4's price bars) and converts them into the
plain dataclasses the backtest engine operates on.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.economic import EconomicObservation, EconomicSeries
from app.models.market import MarketBar
from app.research.data_types import EconomicPoint, PriceBar


def get_price_bars(db: Session, symbol: str, interval: str) -> list[PriceBar]:
    rows = (
        db.execute(
            select(MarketBar)
            .where(MarketBar.symbol == symbol, MarketBar.interval == interval)
            .order_by(MarketBar.bar_time)
        )
        .scalars()
        .all()
    )
    return [
        PriceBar(
            bar_date=row.bar_time.date(),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
        )
        for row in rows
    ]


def get_economic_points(db: Session, series_codes: list[str]) -> dict[str, list[EconomicPoint]]:
    """
    Fetches the FULL point-in-time vintage history for each series — every
    revision ever recorded, not just the latest — since that's what makes
    look-ahead-free backtesting possible (see research/macro_replay.py).
    """
    result: dict[str, list[EconomicPoint]] = {}
    for code in series_codes:
        series = db.execute(
            select(EconomicSeries).where(EconomicSeries.code == code)
        ).scalar_one_or_none()
        if series is None:
            result[code] = []
            continue

        rows = (
            db.execute(
                select(EconomicObservation)
                .where(EconomicObservation.series_id == series.id)
                .order_by(EconomicObservation.observation_date)
            )
            .scalars()
            .all()
        )
        result[code] = [
            EconomicPoint(
                observation_date=row.observation_date,
                value=float(row.value),
                realtime_start=row.realtime_start,
                realtime_end=row.realtime_end,
            )
            for row in rows
        ]
    return result
