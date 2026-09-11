from fastapi import APIRouter

from app.api.v1.endpoints import (
    economic,
    execution,
    learning,
    macro,
    market_data,
    market_state,
    memory,
    opportunities,
    performance,
    positions,
    research,
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
api_router.include_router(performance.router)
api_router.include_router(research.router)
api_router.include_router(memory.router)
api_router.include_router(learning.router)
