"""
Tests for the paper broker adapter. Verifies it fills against REAL ingested
price bars (never fabricated data) with a small, deterministic spread.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.execution.paper_broker import NoPriceDataError, PaperBrokerAdapter
from app.models.market import MarketBar


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_bar(db: Session, close: float) -> None:
    db.add(
        MarketBar(
            symbol="XAUUSD",
            interval="1day",
            bar_time=datetime(2026, 9, 9, tzinfo=UTC),
            open=close,
            high=close,
            low=close,
            close=close,
        )
    )
    db.commit()


def test_paper_fill_uses_real_ingested_price(db_session: Session) -> None:
    _seed_bar(db_session, close=3600.0)
    broker = PaperBrokerAdapter(db=db_session, spread_bps=2.0)

    fill = broker.place_market_order("XAUUSD", "LONG", units=1.0)

    # half_spread = 3600 * 0.0002 / 2 = 0.36; LONG fills above the reference.
    assert fill.filled_price == pytest.approx(3600.36, abs=0.001)


def test_paper_fill_short_fills_below_reference(db_session: Session) -> None:
    _seed_bar(db_session, close=3600.0)
    broker = PaperBrokerAdapter(db=db_session, spread_bps=2.0)

    fill = broker.place_market_order("XAUUSD", "SHORT", units=1.0)

    assert fill.filled_price == pytest.approx(3599.64, abs=0.001)


def test_paper_fill_raises_without_price_data(db_session: Session) -> None:
    broker = PaperBrokerAdapter(db=db_session)
    with pytest.raises(NoPriceDataError):
        broker.place_market_order("XAUUSD", "LONG", units=1.0)
