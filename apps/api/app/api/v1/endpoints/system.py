"""
/api/v1/system — health and readiness endpoints.

`health` never touches the database or Redis: it just confirms the API
process itself is up. `ready` checks downstream dependencies and is what
you'd point a container orchestrator's readiness probe at.
"""
from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter(prefix="/system", tags=["system"])
log = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    environment: str
    time: datetime


class DependencyStatus(BaseModel):
    database: str
    redis: str


class ReadyResponse(BaseModel):
    status: str
    dependencies: DependencyStatus


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        time=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    settings = get_settings()

    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - deliberately broad for a health check
        db_status = "unreachable"
        log.warning("readiness_check_failed", dependency="database", error=str(exc))

    redis_status = "ok"
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
    except Exception as exc:  # noqa: BLE001
        redis_status = "unreachable"
        log.warning("readiness_check_failed", dependency="redis", error=str(exc))

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return ReadyResponse(
        status=overall,
        dependencies=DependencyStatus(database=db_status, redis=redis_status),
    )
