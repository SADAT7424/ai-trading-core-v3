"""
GO OS API — FastAPI entrypoint.

BUILD 01 — Foundation. No broker connections, no live trading, no domain
logic yet. See AGENTS.md and docs/DEVELOPMENT_RULES.md before adding features.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("api_startup", environment=settings.environment)
    yield
    log.info("api_shutdown", environment=settings.environment)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="GO OS — Personal AI-assisted algorithmic trading platform (Foundation stage).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "status": "ok",
        "environment": settings.environment,
        "docs": "/docs",
    }
