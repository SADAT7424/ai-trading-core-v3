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


def test_too_many_vintages_falls_back_to_current_only() -> None:
    """
    High-frequency series like DGS10 can exceed FRED's vintage-date cap when
    requesting full point-in-time history. The provider should fall back to
    a simpler "current values only" request rather than failing outright.
    """
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        if "realtime_start" in params:
            return httpx.Response(
                400,
                json={
                    "error_code": 400,
                    "error_message": (
                        "Bad Request.  There are 5106 vintage dates in the "
                        "specified real-time period: 1776-07-04 to 9999-12-31. "
                        "This exceeds the maximum number of vintage dates "
                        "allowed for this file type (2000)."
                    ),
                },
            )
        # The fallback request has no realtime_start/realtime_end at all.
        return httpx.Response(
            200,
            json={
                "observations": [
                    {
                        "realtime_start": "2026-09-01",
                        "realtime_end": "2026-09-01",
                        "date": "2026-09-01",
                        "value": "4.12",
                    }
                ]
            },
        )

    provider = _make_provider(handler)
    observations = provider.fetch_observations("DGS10")

    assert len(calls) == 2
    assert "realtime_start" in calls[0]
    assert "realtime_start" not in calls[1]
    assert len(observations) == 1
    assert observations[0].value == 4.12
