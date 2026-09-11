"""
Tests for the Twelve Data provider adapter. No real network calls — mock
transport stands in, using the exact response shape confirmed against
Twelve Data's own documentation before this adapter was written.
"""
import httpx
import pytest

from app.data.providers.twelvedata import TwelveDataProvider, TwelveDataProviderError

DAILY_RESPONSE = {
    "meta": {
        "symbol": "XAU/USD",
        "interval": "1day",
        "currency": "USD",
        "exchange_timezone": "UTC",
        "exchange": "",
        "mic_code": "",
        "type": "Physical Currency",
    },
    "values": [
        # Twelve Data returns most-recent-first — the adapter must resort.
        {
            "datetime": "2026-09-10",
            "open": "3610.5",
            "high": "3625.0",
            "low": "3600.0",
            "close": "3618.2",
        },
        {
            "datetime": "2026-09-09",
            "open": "3595.0",
            "high": "3615.0",
            "low": "3590.0",
            "close": "3610.5",
        },
    ],
    "status": "ok",
}


def _make_provider(handler) -> TwelveDataProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return TwelveDataProvider(
        api_key="test-key", base_url="https://api.twelvedata.com", client=client
    )


def test_missing_api_key_fails_fast() -> None:
    with pytest.raises(TwelveDataProviderError, match="TWELVE_DATA_API_KEY is not set"):
        TwelveDataProvider(api_key="", base_url="https://api.twelvedata.com")


def test_fetch_bars_translates_symbol_and_sorts_chronologically() -> None:
    captured_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=DAILY_RESPONSE)

    provider = _make_provider(handler)
    bars = provider.fetch_bars("XAUUSD", "1day", outputsize=2)

    # Canonical "XAUUSD" must be translated to Twelve Data's "XAU/USD".
    assert captured_params["symbol"] == "XAU/USD"

    # Response was most-recent-first; adapter must return chronological order.
    assert len(bars) == 2
    assert bars[0].bar_time < bars[1].bar_time
    assert bars[0].close == 3610.5
    assert bars[1].close == 3618.2
    # Bars carry the CANONICAL symbol, not the provider's.
    assert bars[0].symbol == "XAUUSD"


def test_fetch_bars_handles_missing_volume() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=DAILY_RESPONSE)

    provider = _make_provider(handler)
    bars = provider.fetch_bars("XAUUSD", "1day")
    assert all(bar.volume is None for bar in bars)


def test_error_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"code": 400, "message": "Invalid API key.", "status": "error"}
        )

    provider = _make_provider(handler)
    with pytest.raises(TwelveDataProviderError, match="Invalid API key"):
        provider.fetch_bars("XAUUSD", "1day")
