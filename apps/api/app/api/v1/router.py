from fastapi import APIRouter

from app.api.v1.endpoints import (
    economic,
    execution,
    macro,
    market_data,
    market_state,
    opportunities,
    positions,
    risk,
    system,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(economic.router)
api_router.include_router(macro.router)
api_router.include_router(market_data.router)
api_router.include_router(market_state.router)
api_router.include_router(opportunities.router)
api_router.include_router(risk.router)
api_router.include_router(execution.router)
api_router.include_router(positions.router)
