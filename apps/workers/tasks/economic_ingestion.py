"""
Scheduled economic data ingestion.

The worker deliberately does NOT import the API's database models or
ingestion logic directly — it calls the API over HTTP instead. This keeps
the two services independently deployable and means there is exactly one
place (the API) that owns writes to the database, per AGENTS.md section 4.
"""
import os

import httpx

from celery_app import celery_app

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")

# Initial macro scope, per docs/RAH_OS_Master_Plan.docx section 18.4 —
# a small, gold-relevant watchlist. Expand deliberately, not by default.
WATCHLIST = [
    "CPIAUCSL",  # CPI (headline)
    "UNRATE",  # Unemployment rate
    "FEDFUNDS",  # Effective federal funds rate
    "DGS10",  # 10-Year Treasury yield
]


@celery_app.task(name="tasks.ingest_economic_series")
def ingest_economic_series(series_code: str) -> dict:
    """Ingest a single series by calling the API's ingest endpoint."""
    url = f"{API_BASE_URL}/api/v1/economic/series/{series_code}/ingest"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url)

    if response.status_code != httpx.codes.OK:
        # Don't raise — a single bad series (e.g. missing API key) shouldn't
        # crash the whole scheduled run. Return the error for visibility in
        # Celery's logs/result backend instead.
        return {
            "series_code": series_code,
            "status": "error",
            "detail": response.text,
        }

    return {"series_code": series_code, "status": "ok", **response.json()}


@celery_app.task(name="tasks.ingest_watchlist")
def ingest_watchlist() -> list[str]:
    """Fan out one ingestion task per series in the watchlist."""
    for series_code in WATCHLIST:
        ingest_economic_series.delay(series_code)
    return WATCHLIST
