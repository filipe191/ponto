from fastapi import APIRouter

from app.api.routes import admin, auth, clock, health, mobile

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(clock.router)
api_router.include_router(mobile.router)
api_router.include_router(admin.router)
