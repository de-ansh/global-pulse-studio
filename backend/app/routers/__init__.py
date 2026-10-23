"""Routers package export."""
from app.routers.health import router as health_router
from app.routers.radar import router as radar_router
from app.routers.projects import router as projects_router

__all__ = [
    "health_router",
    "radar_router",
    "projects_router",
]
