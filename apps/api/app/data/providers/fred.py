"""
FRED (Federal Reserve Economic Data) provider adapter.

FRED is used as the first real economic data source because it is free,
requires only a free API key (https://fred.stlouisfed.org/docs/api/api_key.html),
and — critically — supports true point-in-time vintages via `output_type=2`,
which matches the master plan's point-in-time requirement (section 14.2)
far better than most "current value only" free APIs.
"""
from datetime import date

import httpx

from app.core.logging import get_logger
from app.data.providers.base import EconomicDataProvider, ObservationDTO, SeriesMetadataDTO

log = get_logger(__name__)

# FRED encodes "no data yet" / "still current" as these sentinel dates.
_FRED_MIN_DATE = "1776-07-04"
_FRED_MAX_DATE = "9999-12-31"


class FredProviderError(RuntimeError):
    """Raised when FRED returns an error or an unexpected response shape."""


class FredProvider(EconomicDataProvider):
    def __init__(self, api_key: str, base_url: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            # Fail loudly and immediately, not with a confusing 401 later.
            raise FredProviderError(
                "FRED_API_KEY is not set. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html and add it to .env"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        # Allow a client to be injected for testing (see tests/data/test_fred_provider.py).
        self._client = client or httpx.Client(timeout=10.0)

    def fetch_series_metadata(self, series_code: str) -> SeriesMetadataDTO:
        response = self._client.get(
            f"{self._base_url}/series",
            params={"series_id": series_code, "api_key": self._api_key, "file_type": "json"},
        )
        self._raise_for_fred_error(response)
        payload = response.json()
        series_list = payload.get("seriess") or []
        if not series_list:
            raise FredProviderError(f"FRED returned no metadata for series '{series_code}'")
        series = series_list[0]
        return SeriesMetadataDTO(
            code=series["id"],
            name=series["title"],
            frequency=series.get("frequency"),
            units=series.get("units"),
        )

    def fetch_observations(self, series_code: str) -> list[ObservationDTO]:
        response = self._client.get(
            f"{self._base_url}/series/observations",
            params={
                "series_id": series_code,
                "api_key": self._api_key,
                "file_type": "json",
                # A wide realtime_start/realtime_end window with the default
                # output_type (1 — "Observations by Real-Time Period") is
                # what actually returns one flat row per historical vintage.
                #
                # output_type=2 ("by Vintage Date") looks tempting for "give
                # me every vintage" but returns a completely different,
                # pivoted shape — one dynamically-named column per vintage
                # date (e.g. "CPIAUCSL_19940217") instead of a "value" field
                # — which silently produced zero usable rows here. Confirmed
                # against a live response; do not change this without
                # re-checking a real API response shape first.
                "realtime_start": _FRED_MIN_DATE,
                "realtime_end": _FRED_MAX_DATE,
            },
        )
        self._raise_for_fred_error(response)
        payload = response.json()
        raw_observations = payload.get("observations") or []

        results: list[ObservationDTO] = []
        skipped = 0
        for row in raw_observations:
            if row.get("value") in (None, ".", ""):
                skipped += 1
                continue
            try:
                results.append(
                    ObservationDTO(
                        series_code=series_code,
                        observation_date=date.fromisoformat(row["date"]),
                        value=float(row["value"]),
                        realtime_start=date.fromisoformat(row["realtime_start"]),
                        realtime_end=date.fromisoformat(row["realtime_end"]),
                    )
                )
            except (KeyError, ValueError) as exc:
                skipped += 1
                log.warning(
                    "fred_observation_skipped",
                    series_code=series_code,
                    row=row,
                    error=str(exc),
                )

        if skipped:
            log.info("fred_observations_skipped_summary", series_code=series_code, skipped=skipped)

        return results

    @staticmethod
    def _raise_for_fred_error(response: httpx.Response) -> None:
        if response.status_code != httpx.codes.OK:
            raise FredProviderError(
                f"FRED request failed with status {response.status_code}: {response.text[:300]}"
            )