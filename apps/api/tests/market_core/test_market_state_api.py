"""
Integration tests for /api/v1/market/state — seeds synthetic but
realistic-shaped price bars directly into the DB and verifies the whole
pipeline (repository -> calculations -> API response) end to end.
"""
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.market import MarketBar


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


def _seed_trending_bullish_low_vol(db: Session, bars_count: int = 60) -> None:
    """A steady uptrend with small daily ranges -> BULLISH + LOW/NORMAL vol -> TRENDING."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    price = 3000.0
    for i in range(bars_count):
        price += 3.0  # steady climb
        db.add(
            MarketBar(
                symbol="XAUUSD",
                interval="1day",
                bar_time=start + timedelta(days=i),
                open=price - 1,
                high=price + 1.5,
                low=price - 1.5,
                close=price,
            )
        )
    db.commit()


def test_market_state_no_data_returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/market/state/XAUUSD")
    assert response.status_code == 400


def test_market_state_trending_bullish_scenario(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    _seed_trending_bullish_low_vol(db)

    response = client.get("/api/v1/market/state/XAUUSD")
    assert response.status_code == 200
    body = response.json()

    assert body["trend"] == "BULLISH"
    assert body["regime"] == "TRENDING"
    assert body["sma_fast"] > body["sma_slow"]  # fast SMA above slow in an uptrend
    assert body["momentum"] == "POSITIVE"


def test_market_state_respects_interval_param(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    _seed_trending_bullish_low_vol(db)

    # No 4h bars seeded — must 400, not silently fall back to 1day.
    response = client.get("/api/v1/market/state/XAUUSD", params={"interval": "4h"})
    assert response.status_code == 400
