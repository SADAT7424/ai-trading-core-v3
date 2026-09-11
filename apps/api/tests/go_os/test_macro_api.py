"""
Integration tests for /api/v1/macro/regime — seeds synthetic (but
realistic-shaped) economic data directly into the DB and verifies the whole
pipeline (repository -> calculations -> API response) end to end.
"""
from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.economic import DataSource, EconomicObservation, EconomicSeries


def _seed_series(
    db: Session, code: str, points: list[tuple[date, float]]
) -> None:
    source = db.query(DataSource).filter_by(name="TEST").one_or_none()
    if source is None:
        source = DataSource(name="TEST", base_url="https://example.test")
        db.add(source)
        db.flush()

    series = EconomicSeries(source_id=source.id, code=code, name=code)
    db.add(series)
    db.flush()

    for obs_date, value in points:
        db.add(
            EconomicObservation(
                series_id=series.id,
                observation_date=obs_date,
                value=value,
                realtime_start=obs_date,
                realtime_end=date(9999, 12, 31),
            )
        )
    db.commit()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_bullish_scenario(db: Session, today: date) -> None:
    # Inflation rising and high: 5.5% YoY, accelerating over the last 90 days.
    _seed_series(
        db,
        "CPIAUCSL",
        [
            (today - timedelta(days=365), 300.0),
            (today - timedelta(days=90), 314.0),
            (today, 316.5),  # YoY = (316.5-300)/300 = 5.5%
        ],
    )
    # Unemployment rising (weakening labor market) => stagflation-leaning.
    _seed_series(
        db,
        "UNRATE",
        [
            (today - timedelta(days=180), 3.8),
            (today, 4.5),
        ],
    )
    # Fed cutting rates => dovish.
    _seed_series(
        db,
        "FEDFUNDS",
        [
            (today - timedelta(days=180), 5.0),
            (today, 4.0),
        ],
    )
    # Negative real yield (TIPS), directly.
    _seed_series(
        db,
        "DFII10",
        [
            (today - timedelta(days=30), -0.3),
            (today, -0.5),
        ],
    )
    # Breakeven inflation expectations — informational only, not scored yet.
    _seed_series(
        db,
        "T10YIE",
        [
            (today - timedelta(days=30), 2.3),
            (today, 2.4),
        ],
    )
    # USD weakening => bullish contribution.
    _seed_series(
        db,
        "DTWEXBGS",
        [
            (today - timedelta(days=90), 122.0),
            (today, 118.0),
        ],
    )


def test_macro_regime_missing_data_returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/macro/regime")
    assert response.status_code == 400


def test_macro_regime_bullish_gold_scenario(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db_gen = engine()
    db = next(db_gen)
    today = date(2026, 1, 1)
    _seed_bullish_scenario(db, today)

    response = client.get("/api/v1/macro/regime")
    assert response.status_code == 200
    body = response.json()

    assert body["inflation_level"] == "HIGH"
    assert body["employment_condition"] == "WEAKENING"
    assert body["policy_stance"] == "DOVISH"
    assert body["real_yield_level"] == "NEGATIVE"
    assert body["usd_condition"] == "WEAKENING"
    assert body["regime"] == "STAGFLATION"  # high inflation + weakening employment
    assert body["gold_score"]["bias"] == "BULLISH"
    # Negative real yields + high inflation + dovish policy + weak USD all
    # push the same direction, so the total should be strongly positive.
    assert body["gold_score"]["total"] > 0
