"""
Tests for the ingestion service. Uses a fake in-memory provider (not FRED)
so these tests are fast, deterministic, and independent of any real API.
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.data.ingestion.economic import ingest_series
from app.data.providers.base import EconomicDataProvider, ObservationDTO, SeriesMetadataDTO
from app.db.base import Base


class FakeProvider(EconomicDataProvider):
    """A provider double whose responses are controlled entirely by the test."""

    def __init__(self, observations: list[ObservationDTO]) -> None:
        self._observations = observations

    def fetch_series_metadata(self, series_code: str) -> SeriesMetadataDTO:
        return SeriesMetadataDTO(code=series_code, name=f"Fake series {series_code}")

    def fetch_observations(self, series_code: str) -> list[ObservationDTO]:
        return self._observations


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _obs(obs_date: str, value: float, rt_start: str, rt_end: str = "9999-12-31") -> ObservationDTO:
    return ObservationDTO(
        series_code="TEST",
        observation_date=date.fromisoformat(obs_date),
        value=value,
        realtime_start=date.fromisoformat(rt_start),
        realtime_end=date.fromisoformat(rt_end),
    )


def test_ingest_creates_source_series_and_observations(db_session: Session) -> None:
    provider = FakeProvider([_obs("2024-01-01", 100.0, "2024-02-01")])

    summary = ingest_series(
        db=db_session,
        provider=provider,
        source_name="TESTSRC",
        source_base_url="https://example.test",
        series_code="TEST",
    )

    assert summary.fetched == 1
    assert summary.inserted == 1
    assert summary.already_present == 0


def test_ingest_is_idempotent_on_repeated_runs(db_session: Session) -> None:
    provider = FakeProvider([_obs("2024-01-01", 100.0, "2024-02-01")])

    ingest_series(
        db=db_session,
        provider=provider,
        source_name="TESTSRC",
        source_base_url="https://example.test",
        series_code="TEST",
    )
    # Run again with the exact same data — nothing new should be inserted.
    second = ingest_series(
        db=db_session,
        provider=provider,
        source_name="TESTSRC",
        source_base_url="https://example.test",
        series_code="TEST",
    )

    assert second.fetched == 1
    assert second.inserted == 0
    assert second.already_present == 1


def test_ingest_stores_a_new_row_for_a_revision_not_an_overwrite(db_session: Session) -> None:
    """
    Per AGENTS.md section 4, observations are append-only: a revised value
    must produce a NEW row (different realtime_start), never overwrite the
    original — that's what preserves point-in-time history.
    """
    provider = FakeProvider([_obs("2024-01-01", 100.0, "2024-02-01")])
    ingest_series(
        db=db_session,
        provider=provider,
        source_name="TESTSRC",
        source_base_url="https://example.test",
        series_code="TEST",
    )

    # A revision of the same observation_date, with a later realtime_start.
    provider_revised = FakeProvider(
        [
            _obs("2024-01-01", 100.0, "2024-02-01", "2024-02-28"),
            _obs("2024-01-01", 101.5, "2024-03-01"),
        ]
    )
    summary = ingest_series(
        db=db_session,
        provider=provider_revised,
        source_name="TESTSRC",
        source_base_url="https://example.test",
        series_code="TEST",
    )

    # The original vintage already existed; only the new revision is inserted.
    assert summary.fetched == 2
    assert summary.inserted == 1
    assert summary.already_present == 1
