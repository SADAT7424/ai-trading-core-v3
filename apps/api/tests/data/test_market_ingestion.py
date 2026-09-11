"""
Tests for market bar ingestion. Uses a fake in-memory provider, not
Twelve Data — fast, deterministic, no network dependency.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.data.ingestion.market import ingest_bars
from app.data.providers.market_base import BarDTO, MarketDataProvider
from app.db.base import Base


class FakeMarketProvider(MarketDataProvider):
    def __init__(self, bars: list[BarDTO]) -> None:
        self._bars = bars

    def fetch_bars(self, symbol: str, interval: str, outputsize: int = 200) -> list[BarDTO]:
        return self._bars


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _bar(dt: str, close: float) -> BarDTO:
    d = datetime.fromisoformat(dt).replace(tzinfo=UTC)
    return BarDTO(
        symbol="XAUUSD",
        interval="1day",
        bar_time=d,
        open=close,
        high=close,
        low=close,
        close=close,
    )


def test_ingest_inserts_new_bars(db_session: Session) -> None:
    provider = FakeMarketProvider([_bar("2026-09-08", 3600), _bar("2026-09-09", 3610)])
    summary = ingest_bars(db_session, provider, "XAUUSD", "1day")
    assert summary.fetched == 2
    assert summary.inserted == 2
    assert summary.already_present == 0


def test_ingest_is_idempotent(db_session: Session) -> None:
    provider = FakeMarketProvider([_bar("2026-09-08", 3600), _bar("2026-09-09", 3610)])
    ingest_bars(db_session, provider, "XAUUSD", "1day")
    second = ingest_bars(db_session, provider, "XAUUSD", "1day")
    assert second.inserted == 0
    assert second.already_present == 2


def test_ingest_only_adds_genuinely_new_bars(db_session: Session) -> None:
    provider = FakeMarketProvider([_bar("2026-09-08", 3600)])
    ingest_bars(db_session, provider, "XAUUSD", "1day")

    provider2 = FakeMarketProvider([_bar("2026-09-08", 3600), _bar("2026-09-09", 3610)])
    summary = ingest_bars(db_session, provider2, "XAUUSD", "1day")
    assert summary.fetched == 2
    assert summary.inserted == 1
    assert summary.already_present == 1
