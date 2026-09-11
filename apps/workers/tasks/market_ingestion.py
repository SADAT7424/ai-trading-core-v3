"""
Scheduled market price bar ingestion. Same HTTP-to-API pattern as
economic_ingestion.py — see that module's docstring for why.
"""
import os

import httpx

from celery_app import celery_app

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")

# Initial asset/timeframe scope, per docs/RAH_OS_Master_Plan.docx sections
# 18.1/18.2 — XAUUSD only, daily bars only, until this is proven out.
MARKET_WATCHLIST = [
    ("XAUUSD", "1day"),
]


@celery_app.task(name="tasks.ingest_market_bars")
def ingest_market_bars(symbol: str, interval: str) -> dict:
    """Ingest bars for a single symbol/interval by calling the API."""
    url = f"{API_BASE_URL}/api/v1/market/bars/{symbol}/{interval}/ingest"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url)

    if response.status_code != httpx.codes.OK:
        return {
            "symbol": symbol,
            "interval": interval,
            "status": "error",
            "detail": response.text,
        }

    return {"symbol": symbol, "interval": interval, "status": "ok", **response.json()}


@celery_app.task(name="tasks.ingest_market_watchlist")
def ingest_market_watchlist() -> list[list[str]]:
    """Fan out one ingestion task per symbol/interval in the market watchlist."""
    for symbol, interval in MARKET_WATCHLIST:
        ingest_market_bars.delay(symbol, interval)
    return [list(pair) for pair in MARKET_WATCHLIST]
