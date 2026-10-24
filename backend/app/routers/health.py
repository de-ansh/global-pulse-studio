"""Health check and system status router."""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
async def get_health():
    """Liveness probe returning service status and version."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/features")
async def get_features():
    """Which optional features are configured, so the UI can disable buttons instead of failing on click.

    Booleans only, never key material; unlike the bare health probe, this path sits behind auth when enabled.
    """
    return {"ai": bool(settings.GEMINI_API_KEY), "factcheck": bool(settings.FACTCHECK_API_KEY)}
