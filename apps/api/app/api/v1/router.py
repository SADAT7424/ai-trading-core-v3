from fastapi import APIRouter

from app.api.v1.endpoints import economic, macro, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(economic.router)
api_router.include_router(macro.router)
