"""
Integration tests for /api/v1/positions — verifies a filled order
automatically becomes a monitorable position, and that monitoring correctly
holds or closes it based on fresh market/macro data.
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


def _seed_bullish_macro(db: Session, today: date) -> None:
    _seed_economic(db, "CPIAUCSL", [(today - timedelta(days=365), 300.0), (today, 316.5)])
    _seed_economic(db, "UNRATE", [(today - timedelta(days=180), 3.8), (today, 3.5)])
    _seed_economic(db, "FEDFUNDS", [(today - timedelta(days=180), 5.0), (today, 4.0)])
    _seed_economic(db, "DFII10", [(today - timedelta(days=30), -0.3), (today, -0.5)])
    _seed_economic(db, "T10YIE", [(today - timedelta(days=30), 2.3), (today, 2.4)])
    _seed_economic(db, "DTWEXBGS", [(today - timedelta(days=90), 122.0), (today, 118.0)])


def _seed_bars(db: Session, closes: list[float], start_day: int = 0) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i, close in enumerate(closes):
        db.add(
            MarketBar(
                symbol="XAUUSD",
                interval="1day",
                bar_time=start + timedelta(days=start_day + i),
                open=close - 1,
                high=close + 1.5,
                low=close - 1.5,
                close=close,
            )
        )
    db.commit()


def _open_a_position(client: TestClient, db: Session, today: date) -> dict:
    """Runs the full pipeline to get exactly one FILLED order -> Position."""
    _seed_bullish_macro(db, today)
    closes = [3000.0 + i * 4.0 for i in range(59)] + [3000.0 + 58 * 4.0 - 2]  # ends in a pullback
    _seed_bars(db, closes)

    response = client.post("/api/v1/execution/orders/XAUUSD")
    body = response.json()
    assert body["status"] == "FILLED", f"Test setup didn't produce a fill: {body}"
    return body


def test_list_positions_empty_initially(client: TestClient) -> None:
    response = client.get("/api/v1/positions")
    assert response.status_code == 200
    assert response.json() == []


def test_filled_order_creates_an_open_position(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    _open_a_position(client, db, today)

    response = client.get("/api/v1/positions")
    assert response.status_code == 200
    positions = response.json()
    assert len(positions) == 1
    assert positions[0]["status"] == "OPEN"
    assert positions[0]["entry_thesis"]  # non-empty — the thesis was captured
    assert positions[0]["target_price"] != positions[0]["entry_price"]


def test_monitor_holds_when_thesis_still_intact(client: TestClient) -> None:
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    order = _open_a_position(client, db, today)

    positions = client.get("/api/v1/positions").json()
    position_id = positions[0]["id"]

    # Add one more bar, close to the same level — nothing dramatic changes.
    db.add(
        MarketBar(
            symbol="XAUUSD",
            interval="1day",
            bar_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=60),
            open=order["filled_price"],
            high=order["filled_price"] + 1,
            low=order["filled_price"] - 1,
            close=order["filled_price"],
        )
    )
    db.commit()

    response = client.post(f"/api/v1/positions/{position_id}/monitor")
    assert response.status_code == 200
    body = response.json()
    assert body["exit_action"] == "HOLD"
    assert body["position"]["status"] == "OPEN"


def test_monitor_closes_on_stop_breach_even_with_healthy_macro(client: TestClient) -> None:
    """The hard-stop-always-wins rule, proven through the real API."""
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    order = _open_a_position(client, db, today)

    positions = client.get("/api/v1/positions").json()
    position_id = positions[0]["id"]
    stop_price = positions[0]["initial_stop_price"]

    # Price crashes straight through the stop. Macro data is untouched —
    # still bullish — proving the stop wins regardless.
    db.add(
        MarketBar(
            symbol="XAUUSD",
            interval="1day",
            bar_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=60),
            open=order["filled_price"],
            high=order["filled_price"],
            low=stop_price - 5,
            close=stop_price - 1,  # below the stop
        )
    )
    db.commit()

    response = client.post(f"/api/v1/positions/{position_id}/monitor")
    assert response.status_code == 200
    body = response.json()
    assert body["exit_action"] == "EXIT"
    assert body["exit_reason"] == "STOP_LOSS"
    assert body["position"]["status"] == "CLOSED"
    assert body["position"]["realized_pnl"] is not None


def test_monitor_nonexistent_position_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/positions/does-not-exist/monitor")
    assert response.status_code == 404


def test_risk_engine_sees_real_open_positions(client: TestClient) -> None:
    """
    The correctness fix: after opening a position, a fresh risk evaluation
    for the SAME symbol must see it counted toward open_positions_count —
    it must not silently assume a flat account.
    """
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    _open_a_position(client, db, today)

    # Set max_open_positions to exactly 1 — the existing open position alone
    # should now be enough to block any further trade.
    client.put("/api/v1/risk/config", json={"max_open_positions": 1})

    response = client.post("/api/v1/risk/evaluate-trade/XAUUSD")
    body = response.json()
    if body["direction"] != "NONE":
        assert body["approved"] is False
        assert "MAX_OPEN_POSITIONS_REACHED" in body["reasons"]


def test_daily_loss_limit_blocks_after_a_real_closed_loss(client: TestClient) -> None:
    """
    Close a position at a real loss, set a low daily loss limit, and verify
    a subsequent evaluation is blocked — proving the daily P&L is read from
    real position history, not assumed to be zero.
    """
    engine = app.dependency_overrides[get_db]
    db = next(engine())
    today = date(2026, 9, 9)
    order = _open_a_position(client, db, today)

    positions = client.get("/api/v1/positions").json()
    position_id = positions[0]["id"]
    stop_price = positions[0]["initial_stop_price"]

    # Force a stop-out to create a real, recorded loss today.
    db.add(
        MarketBar(
            symbol="XAUUSD",
            interval="1day",
            bar_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=60),
            open=order["filled_price"],
            high=order["filled_price"],
            low=stop_price - 5,
            close=stop_price - 1,
        )
    )
    db.commit()
    monitor_response = client.post(f"/api/v1/positions/{position_id}/monitor").json()
    assert monitor_response["position"]["status"] == "CLOSED"
    assert monitor_response["position"]["realized_pnl"] < 0

    # An extremely tight daily loss limit — the loss just recorded should
    # already exceed it.
    client.put("/api/v1/risk/config", json={"max_daily_loss_pct": 0.01})

    response = client.post("/api/v1/risk/evaluate-trade/XAUUSD")
    body = response.json()
    if body["direction"] != "NONE":
        assert body["approved"] is False
        assert "MAX_DAILY_LOSS_REACHED" in body["reasons"]
