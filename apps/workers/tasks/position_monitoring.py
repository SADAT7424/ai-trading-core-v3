"""
Scheduled position monitoring. Same HTTP-to-API pattern as the other
scheduled tasks — see economic_ingestion.py's docstring for why.
"""
import os

import httpx

from celery_app import celery_app

API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000")


@celery_app.task(name="tasks.monitor_all_positions")
def monitor_all_positions() -> dict:
    url = f"{API_BASE_URL}/api/v1/positions/monitor-all"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url)

    if response.status_code != httpx.codes.OK:
        return {"status": "error", "detail": response.text}

    results = response.json()
    return {
        "status": "ok",
        "positions_checked": len(results),
        "exits": [r["position"]["id"] for r in results if r["exit_action"] == "EXIT"],
    }
