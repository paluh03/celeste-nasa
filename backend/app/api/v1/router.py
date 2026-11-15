from fastapi import APIRouter

from app.api.v1 import astronauts, measurements, monitoring
from app.modules.cortisol import router as cortisol_router
from app.modules.mental import router as mental_router
from app.modules.radiation import router as radiation_router

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(astronauts.router)
api_router.include_router(measurements.router)
api_router.include_router(cortisol_router.router)
api_router.include_router(radiation_router.router)
api_router.include_router(mental_router.router)
