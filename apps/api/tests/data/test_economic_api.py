"""
API tests for /api/v1/economic. Uses a real SQLite database file (not the
production Postgres) via dependency override — no network calls, no FRED.
"""
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.data.ingestion.economic import ingest_series
from app.data.providers.base import EconomicDataProvider, ObservationDTO, SeriesMetadataDTO
from app.db.base import Base
from app.db.session import get_db
from app.main import app


class FakeProvider(EconomicDataProvider):
    def __init__(self, observations: list[ObservationDTO]) -> None:
        self._observations = observations

    def fetch_series_metadata(self, series_code: str) -> SeriesMetadataDTO:
        return SeriesMetadataDTO(code=series_code, name="Fake Test Series")

    def fetch_observations(self, series_code: str) -> list[ObservationDTO]:
        return self._observations


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # TestClient dispatches sync endpoints to a worker thread; a plain
        # SQLite ":memory:" DB is per-connection, so without a shared
        # StaticPool the endpoint would see a different, empty database
        # than the one this fixture just seeded.
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Pre-seed data directly, bypassing the /ingest endpoint (which would
    # need a real FRED_API_KEY) — these tests exercise the read endpoints.
    with TestingSessionLocal() as db:
        provider = FakeProvider(
            [
                ObservationDTO(
                    series_code="TEST",
                    observation_date="2024-01-01",
                    value=100.0,
                    realtime_start="2024-02-01",
                    realtime_end="2024-02-29",
                ),
                ObservationDTO(
                    series_code="TEST",
                    observation_date="2024-01-01",
                    value=101.5,
                    realtime_start="2024-03-01",
                    realtime_end="9999-12-31",
                ),
            ]
        )
        ingest_series(
            db=db,
            provider=provider,
            source_name="TESTSRC",
            source_base_url="https://example.test",
            series_code="TEST",
        )

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_unknown_series_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/economic/series/DOES_NOT_EXIST/observations")
    assert response.status_code == 404


def test_latest_observations_returns_most_recent_vintage(client: TestClient) -> None:
    response = client.get("/api/v1/economic/series/TEST/observations")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["value"] == 101.5  # the later revision, not the original


def test_as_of_query_returns_the_value_known_at_that_time(client: TestClient) -> None:
    # As of Feb 15, only the ORIGINAL vintage existed — the revision hadn't
    # been published yet. This is the point-in-time guarantee in action.
    response = client.get("/api/v1/economic/series/TEST/observations/as-of/2024-02-15")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["value"] == 100.0

    # As of Mar 15, the revision is what was known.
    response = client.get("/api/v1/economic/series/TEST/observations/as-of/2024-03-15")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["value"] == 101.5
