"""
Twelve Data provider adapter for market price bars.

Free tier, real API key required (https://twelvedata.com/pricing — the free
plan is genuinely free, no card required). Response shape confirmed against
Twelve Data's own published documentation before writing this, specifically
to avoid a repeat of the FRED output_type surprise (see fred.py).
"""
from datetime import datetime

import httpx

from app.core.logging import get_logger
from app.data.providers.market_base import BarDTO, MarketDataProvider

log = get_logger(__name__)

# This system's canonical symbols (no slash) -> Twelve Data's own symbol format.
_SYMBOL_MAP = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
}


class TwelveDataProviderError(RuntimeError):
    """Raised when Twelve Data returns an error or an unexpected response shape."""


class TwelveDataProvider(MarketDataProvider):
    def __init__(self, api_key: str, base_url: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise TwelveDataProviderError(
                "TWELVE_DATA_API_KEY is not set. Get a free key at "
                "https://twelvedata.com/pricing and add it to .env"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=10.0)

    def fetch_bars(self, symbol: str, interval: str, outputsize: int = 200) -> list[BarDTO]:
        provider_symbol = _SYMBOL_MAP.get(symbol, symbol)
        response = self._client.get(
            f"{self._base_url}/time_series",
            params={
                "symbol": provider_symbol,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self._api_key,
            },
        )
        payload = response.json()

        if response.status_code != httpx.codes.OK or payload.get("status") == "error":
            raise TwelveDataProviderError(
                f"Twelve Data request failed "
                f"(status {response.status_code}): {payload.get('message', response.text[:300])}"
            )

        raw_values = payload.get("values") or []
        bars: list[BarDTO] = []
        skipped = 0
        for row in raw_values:
            try:
                bars.append(
                    BarDTO(
                        symbol=symbol,
                        interval=interval,
                        bar_time=datetime.fromisoformat(row["datetime"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=(
                            float(row["volume"])
                            if row.get("volume") not in (None, "")
                            else None
                        ),
                    )
                )
            except (KeyError, ValueError) as exc:
                skipped += 1
                log.warning(
                    "twelvedata_bar_skipped",
                    symbol=symbol,
                    interval=interval,
                    row=row,
                    error=str(exc),
                )

        if skipped:
            log.info(
                "twelvedata_bars_skipped_summary", symbol=symbol, interval=interval, skipped=skipped
            )

        # Twelve Data returns most-recent-first; normalize to chronological
        # order so downstream indicator math (SMA, ATR, ROC) can assume it.
        bars.sort(key=lambda b: b.bar_time)
        return bars
