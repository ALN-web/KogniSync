from fastapi import APIRouter

from app.api.v1 import bookings, copilot, disruptions, health, journeys, ops

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(journeys.router)
api_router.include_router(bookings.router)
api_router.include_router(disruptions.router)
api_router.include_router(copilot.router)
api_router.include_router(ops.router)
