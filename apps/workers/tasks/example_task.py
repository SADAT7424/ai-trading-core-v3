"""
Placeholder task proving the worker pipeline is wired up correctly.

Replace/remove once real Stage 2 (Data Infrastructure) tasks — economic
calendar polling, market data ingestion — are added.
"""
from celery_app import celery_app


@celery_app.task(name="tasks.ping")
def ping() -> str:
    return "pong"
