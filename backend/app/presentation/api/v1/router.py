from fastapi import APIRouter

from .endpoints.forecast import router as forecast_router
from .endpoints.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(forecast_router, tags=["Forecast"])
