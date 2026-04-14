"""
API Routers for the MARS NewsPulse backend.

Each router module handles a specific domain of functionality.
"""

from fastapi import APIRouter

from routers.health import router as health_router
from routers.files import router as files_router
from routers.credentials import router as credentials_router
from routers.newspulse import router as newspulse_router
from routers.models import router as models_router


def register_routers(app):
    """Register all routers with the FastAPI application."""
    app.include_router(health_router)
    app.include_router(files_router)
    app.include_router(credentials_router)
    app.include_router(newspulse_router)  # Industry News & Sentiment Pulse
    app.include_router(models_router)  # Centralized model configuration


__all__ = [
    "register_routers",
    "health_router",
    "files_router",
    "credentials_router",
    "newspulse_router",
    "models_router",
]
