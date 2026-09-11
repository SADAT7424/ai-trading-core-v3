"""
Database access for the Macro Regime Engine. Kept separate from
calculations.py so the classification logic stays pure and DB-free (see
that module's docstring).
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.economic import EconomicObservation, EconomicSeries


class SeriesNotIngestedError(Exception):
    def __init__(self, series_code: str) -> None:
        self.series_code = series_code
        super().__init__(
            f"Series '{series_code}' has not been ingested yet. "
            f"POST /api/v1/economic/series/{series_code}/ingest first."
        )


@dataclass
class SeriesPoint:
    observation_date: date
    value: float


def _latest_known_value_per_date(
    db: Session, series_id: str
) -> dict[date, EconomicObservation]:
    """As in the /observations endpoint: the most recent vintage for each date."""
    rows = (
        db.execute(
            select(EconomicObservation)
            .where(EconomicObservation.series_id == series_id)
            .order_by(EconomicObservation.observation_date, EconomicObservation.realtime_start)
        )
        .scalars()
        .all()
    )
    latest_by_date: dict[date, EconomicObservation] = {}
    for row in rows:
        latest_by_date[row.observation_date] = row
    return latest_by_date


def get_latest_point(db: Session, series_code: str) -> SeriesPoint:
    series = db.execute(
        select(EconomicSeries).where(EconomicSeries.code == series_code)
    ).scalar_one_or_none()
    if series is None:
        raise SeriesNotIngestedError(series_code)

    by_date = _latest_known_value_per_date(db, series.id)
    if not by_date:
        raise SeriesNotIngestedError(series_code)

    latest_date = max(by_date)
    return SeriesPoint(observation_date=latest_date, value=float(by_date[latest_date].value))


def get_point_near(
    db: Session, series_code: str, target_date: date, tolerance_days: int = 45
) -> SeriesPoint | None:
    """
    The observation whose date is closest to `target_date`, within
    `tolerance_days`. Used for trend/YoY calculations. Returns None (not an
    error) if nothing falls within tolerance — trend calculations should
    degrade gracefully rather than fail hard when history is short.
    """
    series = db.execute(
        select(EconomicSeries).where(EconomicSeries.code == series_code)
    ).scalar_one_or_none()
    if series is None:
        raise SeriesNotIngestedError(series_code)

    by_date = _latest_known_value_per_date(db, series.id)
    if not by_date:
        return None

    closest_date = min(by_date, key=lambda d: abs((d - target_date).days))
    if abs((closest_date - target_date).days) > tolerance_days:
        return None

    return SeriesPoint(observation_date=closest_date, value=float(by_date[closest_date].value))


def get_year_over_year_change(
    db: Session, series_code: str
) -> tuple[SeriesPoint, float] | None:
    """Returns (latest point, YoY % change) or None if a year-ago point isn't available."""
    latest = get_latest_point(db, series_code)
    year_ago = get_point_near(db, series_code, latest.observation_date - timedelta(days=365))
    if year_ago is None or year_ago.value == 0:
        return None
    pct_change = ((latest.value - year_ago.value) / abs(year_ago.value)) * 100
    return latest, pct_change


def get_recent_trend_change(
    db: Session, series_code: str, lookback_days: int = 180
) -> tuple[SeriesPoint, float] | None:
    """Returns (latest point, raw change vs ~lookback_days ago) or None if unavailable."""
    latest = get_latest_point(db, series_code)
    earlier = get_point_near(
        db, series_code, latest.observation_date - timedelta(days=lookback_days)
    )
    if earlier is None:
        return None
    return latest, latest.value - earlier.value
