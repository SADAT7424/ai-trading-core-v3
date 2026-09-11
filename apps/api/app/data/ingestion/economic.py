"""
Economic data ingestion service.

This is deliberately provider-agnostic: it depends only on
`EconomicDataProvider` (app/data/providers/base.py), never on FRED directly.
Per AGENTS.md, this is plain deterministic code — no AI involvement in
deciding what gets written to the database.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.data.providers.base import EconomicDataProvider
from app.models.economic import DataSource, EconomicObservation, EconomicSeries

log = get_logger(__name__)


@dataclass
class IngestSummary:
    series_code: str
    fetched: int
    inserted: int
    already_present: int


def get_or_create_source(db: Session, name: str, base_url: str) -> DataSource:
    source = db.execute(select(DataSource).where(DataSource.name == name)).scalar_one_or_none()
    if source is not None:
        return source
    source = DataSource(name=name, base_url=base_url)
    db.add(source)
    db.flush()  # assign an id without committing yet
    return source


def get_or_create_series(
    db: Session, source: DataSource, provider: EconomicDataProvider, series_code: str
) -> EconomicSeries:
    series = db.execute(
        select(EconomicSeries).where(
            EconomicSeries.source_id == source.id, EconomicSeries.code == series_code
        )
    ).scalar_one_or_none()
    if series is not None:
        return series

    metadata = provider.fetch_series_metadata(series_code)
    series = EconomicSeries(
        source_id=source.id,
        code=metadata.code,
        name=metadata.name,
        frequency=metadata.frequency,
        units=metadata.units,
    )
    db.add(series)
    db.flush()
    return series


def ingest_series(
    db: Session,
    provider: EconomicDataProvider,
    source_name: str,
    source_base_url: str,
    series_code: str,
) -> IngestSummary:
    """
    Fetch and store the full point-in-time vintage history for one series.

    Safe to call repeatedly: already-stored vintages (identified by
    `(series_id, observation_date, realtime_start)`) are left untouched, not
    duplicated or overwritten — see AGENTS.md section 4.
    """
    source = get_or_create_source(db, source_name, source_base_url)
    series = get_or_create_series(db, source, provider, series_code)

    observations = provider.fetch_observations(series_code)

    existing_keys: set[tuple[object, object]] = {
        (row.observation_date, row.realtime_start)
        for row in db.execute(
            select(
                EconomicObservation.observation_date, EconomicObservation.realtime_start
            ).where(EconomicObservation.series_id == series.id)
        ).all()
    }

    inserted = 0
    for obs in observations:
        key = (obs.observation_date, obs.realtime_start)
        if key in existing_keys:
            continue
        db.add(
            EconomicObservation(
                series_id=series.id,
                observation_date=obs.observation_date,
                value=obs.value,
                realtime_start=obs.realtime_start,
                realtime_end=obs.realtime_end,
            )
        )
        existing_keys.add(key)
        inserted += 1

    db.commit()

    summary = IngestSummary(
        series_code=series_code,
        fetched=len(observations),
        inserted=inserted,
        already_present=len(observations) - inserted,
    )
    log.info(
        "economic_series_ingested",
        series_code=series_code,
        fetched=summary.fetched,
        inserted=summary.inserted,
        already_present=summary.already_present,
    )
    return summary
