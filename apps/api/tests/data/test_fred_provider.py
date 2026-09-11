"""
Tests for the FRED provider adapter. No real network calls are made — a
mock httpx transport stands in for FRED's API, per AGENTS.md testing rules.
"""
import httpx
import pytest

from app.data.providers.base import ObservationDTO, SeriesMetadataDTO
from app.data.providers.fred import FredProvider, FredProviderError

SERIES_RESPONSE = {
    "seriess": [
        {
            "id": "CPIAUCSL",
            "title": "Consumer Price Index for All Urban Consumers",
            "frequency": "Monthly",
            "units": "Index 1982-1984=100",
        }
    ]
}

OBSERVATIONS_RESPONSE = {
    "observations": [
        {
            "realtime_start": "2024-02-01",
            "realtime_end": "2024-02-29",
            "date": "2024-01-01",
            "value": "308.417",
        },
        {
            # A later vintage of the SAME observation_date — a revision.
            "realtime_start": "2024-03-01",
            "realtime_end": "9999-12-31",
            "date": "2024-01-01",
            "value": "308.521",
        },
        {
            # Missing value, as FRED encodes it — must be skipped, not crash.
            "realtime_start": "2024-03-01",
            "realtime_end": "9999-12-31",
            "date": "2024-02-01",
            "value": ".",
        },
    ]
}


def _make_provider(handler) -> FredProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return FredProvider(
        api_key="test-key", base_url="https://api.stlouisfed.org/fred", client=client
    )


def test_missing_api_key_fails_fast() -> None:
    with pytest.raises(FredProviderError, match="FRED_API_KEY is not set"):
        FredProvider(api_key="", base_url="https://api.stlouisfed.org/fred")


def test_fetch_series_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/series")
        return httpx.Response(200, json=SERIES_RESPONSE)

    provider = _make_provider(handler)
    metadata = provider.fetch_series_metadata("CPIAUCSL")

    assert metadata == SeriesMetadataDTO(
        code="CPIAUCSL",
        name="Consumer Price Index for All Urban Consumers",
        frequency="Monthly",
        units="Index 1982-1984=100",
    )


def test_fetch_observations_returns_all_vintages_and_skips_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/series/observations")
        return httpx.Response(200, json=OBSERVATIONS_RESPONSE)

    provider = _make_provider(handler)
    observations = provider.fetch_observations("CPIAUCSL")

    # Two valid rows; the "." missing value row must be silently skipped.
    assert len(observations) == 2
    assert observations[0] == ObservationDTO(
        series_code="CPIAUCSL",
        observation_date="2024-01-01",
        value=308.417,
        realtime_start="2024-02-01",
        realtime_end="2024-02-29",
    )
    assert observations[1].value == 308.521


def test_fred_error_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request. Invalid API key.")

    provider = _make_provider(handler)
    with pytest.raises(FredProviderError, match="FRED request failed"):
        provider.fetch_series_metadata("CPIAUCSL")
