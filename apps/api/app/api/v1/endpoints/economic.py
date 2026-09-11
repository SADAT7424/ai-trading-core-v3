"""
/api/v1/economic — read access to stored economic series, plus a manual
ingestion trigger for convenience during development.

The point-in-time endpoint (`/as-of/{as_of_date}`) exists specifically to
prove the thing this whole data model is for: answering "what did we know on
date X", not just "what's the latest revised number today."
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data.ingestion.economic import ingest_series
from app.data.providers.fred import FredProvider, FredProviderError
from app.db.session import get_db
from app.models.economic import EconomicObservation, EconomicSeries

router = APIRouter(prefix="/economic", tags=["economic"])

FRED_SOURCE_NAME = "FRED"


class ObservationResponse(BaseModel):
    observation_date: date
    value: float
    realtime_start: date
    realtime_end: date


class IngestResponse(BaseModel):
    series_code: str
    fetched: int
    inserted: int
    already_present: int


def _get_series_or_404(db: Session, series_code: str) -> EconomicSeries:
    series = db.execute(
        select(EconomicSeries).where(EconomicSeries.code == series_code)
    ).scalar_one_or_none()
    if series is None:
        raise HTTPException(
            status_code=404,
            detail=f"Series '{series_code}' has not been ingested yet. "
            f"POST /economic/series/{series_code}/ingest first.",
        )
    return series


@router.post("/series/{series_code}/ingest", response_model=IngestResponse)
def trigger_ingest(series_code: str, db: Session = Depends(get_db)) -> IngestResponse:
    settings = get_settings()
    try:
        provider = FredProvider(api_key=settings.fred_api_key, base_url=settings.fred_base_url)
        summary = ingest_series(
            db=db,
            provider=provider,
            source_name=FRED_SOURCE_NAME,
            source_base_url=settings.fred_base_url,
            series_code=series_code,
        )
    except FredProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IngestResponse(
        series_code=summary.series_code,
        fetched=summary.fetched,
        inserted=summary.inserted,
        already_present=summary.already_present,
    )


@router.get("/series/{series_code}/observations", response_model=list[ObservationResponse])
def get_latest_observations(
    series_code: str, db: Session = Depends(get_db)
) -> list[ObservationResponse]:
    """The most recent known vintage of every observation_date — i.e. today's view."""
    series = _get_series_or_404(db, series_code)

    rows = db.execute(
        select(EconomicObservation)
        .where(EconomicObservation.series_id == series.id)
        .order_by(EconomicObservation.observation_date, EconomicObservation.realtime_start)
    ).scalars().all()

    latest_by_date: dict[date, EconomicObservation] = {}
    for row in rows:
        latest_by_date[row.observation_date] = row  # later realtime_start overwrites earlier

    return [
        ObservationResponse(
            observation_date=obs.observation_date,
            value=float(obs.value),
            realtime_start=obs.realtime_start,
            realtime_end=obs.realtime_end,
        )
        for obs in sorted(latest_by_date.values(), key=lambda o: o.observation_date)
    ]


@router.get(
    "/series/{series_code}/observations/as-of/{as_of_date}",
    response_model=list[ObservationResponse],
)
def get_observations_as_of(
    series_code: str, as_of_date: date, db: Session = Depends(get_db)
) -> list[ObservationResponse]:
    """
    Point-in-time query: for every observation_date, the vintage of the value
    that was actually known as of `as_of_date` — not today's revised number.
    This is what protects a future backtester from look-ahead bias.
    """
    series = _get_series_or_404(db, series_code)

    rows = db.execute(
        select(EconomicObservation)
        .where(
            EconomicObservation.series_id == series.id,
            EconomicObservation.realtime_start <= as_of_date,
            EconomicObservation.realtime_end >= as_of_date,
        )
        .order_by(EconomicObservation.observation_date)
    ).scalars().all()

    return [
        ObservationResponse(
            observation_date=obs.observation_date,
            value=float(obs.value),
            realtime_start=obs.realtime_start,
            realtime_end=obs.realtime_end,
        )
        for obs in rows
    ]
