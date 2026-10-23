"""FastAPI application factory, lifespan lifecycle, and middleware configuration."""
import asyncio
import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import health_router, radar_router, projects_router
from app.routers.radar import scheduled_scans

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for database table creation and seed initialization."""
    await init_db()
    task = asyncio.create_task(scheduled_scans(settings.SCAN_INTERVAL_MINUTES)) if settings.SCAN_INTERVAL_MINUTES > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Geopolitical and global affairs research platform for long-form video essay creators.",
    lifespan=lifespan,
)

@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """Require HTTP Basic credentials for everything except the health probe, when a password is set."""
    if not settings.AUTH_PASSWORD or request.method == "OPTIONS" or request.url.path == "/api/health":
        return await call_next(request)
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    try:
        user, _, password = base64.b64decode(encoded).decode().partition(":")
    except (ValueError, UnicodeDecodeError):
        user = password = ""
    ok_user = secrets.compare_digest(user.encode(), settings.AUTH_USERNAME.encode())
    ok_pass = secrets.compare_digest(password.encode(), settings.AUTH_PASSWORD.encode())
    if scheme.lower() == "basic" and ok_user and ok_pass:
        return await call_next(request)
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Global Pulse Studio"'})


# CORS configuration (added after auth so it wraps it and preflights stay unauthenticated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(radar_router)
app.include_router(projects_router)

# Mount Vite production assets (only the built bundle; never the frontend source tree)
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
async def root(request: Request):
    """Serve web dashboard for browsers, or JSON metadata for API clients."""
    accept = request.headers.get("accept", "")
    dist_index = FRONTEND_DIST / "index.html"
    legacy_index = FRONTEND_DIR / "index.html"
    index_file = dist_index if dist_index.exists() else legacy_index

    if "text/html" in accept and index_file.exists():
        return FileResponse(index_file)
    return {
        "platform": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "radar_api": "/api/radar/clusters",
        "projects_api": "/api/projects",
    }
