"""
GO OS Celery application — foundation stage.

Real workers (economic calendar ingestion, market data ingestion, news
processing, backtesting jobs, AI analysis, scheduled calculations) are added
starting at Build Stage 2. This stage only proves the worker process, broker
connection, and task-dispatch pattern work end-to-end.
"""
import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "go_os",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.example_task", "tasks.economic_ingestion", "tasks.market_ingestion"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "ingest-economic-watchlist-daily": {
            "task": "tasks.ingest_watchlist",
            # Once a day is plenty for macro series that update
            # monthly/quarterly — no point hammering FRED more often.
            "schedule": 24 * 60 * 60.0,
        },
        "ingest-market-watchlist-daily": {
            "task": "tasks.ingest_market_watchlist",
            # Daily bars only need a daily pull. Twelve Data's free tier has
            # a real request quota — this schedule respects that on purpose.
            "schedule": 24 * 60 * 60.0,
        },
    },
)
