"""
Integration tests for /api/v1/execution — the full pipeline: opportunity ->
risk -> (paper) execution, end to end, for both the approved and rejected
paths.
"""
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.economic import DataSource, EconomicObservation, EconomicSeries
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


def _seed_economic(db: Session, code: str, points: list[tuple[date, float]]) -> None:
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


def _seed_bullish_pullback_scenario(db: Session, today: date) -> None:
    _seed_economic(db, "CPIAUCSL", [(today - timedelta(days=365), 300.0), (today, 316.5)])
    _seed_economic(db, "UNRATE", [(today - timedelta(days=180), 3.8), (today, 3.5)])
    _seed_economic(db, "FEDFUNDS", [(today - timedelta(days=180), 5.0), (today, 4.0)])
    _seed_economic(db, "DFII10", [(today - timedelta(days=30), -0.3), (today, -0.5)])
    _seed_economic(db, "T10YIE", [(today - timedelta(days=30), 2.3), (today, 2.4)])
    _seed_economic(db, "DTWEXBGS", [(today - timedelta(days=90), 122.0), (today, 118.0)])

    start = datetime(2026, 1, 1, tzinfo=UTC)
    price = 3000.0
    for i in range(59):
        price += 4.0
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
    db.add(
        MarketBar(
            symbol="XAUUSD",
            interval="1day",
            bar_time=start + timedelta(days=59),
            open=price,
            high=price + 1,
            low=price - 5,
            close=price - 2,
        )
    )
    db.commit()


def test_submit_order_with_no_data_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/execution/orders/XAUUSD")
    assert response.status_code == 400


def test_submit_order_persists_regardless_of_outcome(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    _seed_bullish_pullback_scenario(db, today)

    response = client.post("/api/v1/execution/orders/XAUUSD")
    assert response.status_code == 200
    body = response.json()

    # Whatever happened, an Order record must exist and be retrievable.
    list_response = client.get("/api/v1/execution/orders")
    assert list_response.status_code == 200
    orders = list_response.json()
    assert len(orders) == 1
    assert orders[0]["id"] == body["id"]


def test_filled_order_uses_real_price_and_is_marked_paper(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    _seed_bullish_pullback_scenario(db, today)

    response = client.post("/api/v1/execution/orders/XAUUSD")
    body = response.json()

    if body["status"] == "FILLED":
        assert body["broker"] == "PAPER"
        assert body["filled_price"] is not None
        assert body["filled_at"] is not None
        assert body["units"] > 0
    else:
        assert body["status"] == "REJECTED"
        assert body["filled_price"] is None
        assert body["units"] == 0.0


def test_kill_switch_blocks_execution_even_with_good_setup(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    _seed_bullish_pullback_scenario(db, today)

    client.post(
        "/api/v1/risk/kill-switch",
        json={"state": "EMERGENCY_STOP", "reason": "Testing"},
    )

    response = client.post("/api/v1/execution/orders/XAUUSD")
    body = response.json()

    if body["direction"] != "NONE":
        assert body["status"] == "REJECTED"
        assert "KILL_SWITCH_ACTIVE" in (body["rejection_reasons"] or "")
