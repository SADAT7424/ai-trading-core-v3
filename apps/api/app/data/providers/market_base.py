"""
Provider interface for market price data — separate from the economic data
provider interface (app/data/providers/base.py) since the shapes and
semantics are different. Same pattern though: business logic depends only
on this interface, never on a concrete provider.
"""
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class BarDTO(BaseModel):
    """One OHLC price bar, provider-agnostic."""

    symbol: str  # canonical format, e.g. "XAUUSD" — no slash
    interval: str  # e.g. "1day", "1h"
    bar_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_bars(self, symbol: str, interval: str, outputsize: int = 200) -> list[BarDTO]:
        """
        Fetch up to `outputsize` most recent bars for `symbol` at `interval`.
        `symbol` is in this system's canonical format (e.g. "XAUUSD"); the
        adapter is responsible for translating to/from its own format.
        """
