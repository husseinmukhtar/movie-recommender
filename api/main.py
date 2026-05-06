"""
api/main.py
FastAPI application factory.
Startup: initialises DB + loads ML models.
All routers registered here.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from api.model_registry import try_load_engine
from api.routers.auth import router as auth_router
from api.routers.ratings import events_router, ratings_router
from api.routers.recommendations import router as recs_router
from api.routers.reviews import router as reviews_router
from config import get_settings
from data.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger   = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    logger.info("Initialising database …")
    init_db()

    logger.info("Loading ML models …")
    loaded = try_load_engine()
    if loaded:
        logger.info("ML engine ready ✓")
    else:
        logger.warning("ML engine NOT loaded — run training first")

    yield   # app is live

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("Shutting down …")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Personalised ML Movie Recommendation System API. "
            "Hybrid collaborative + content-based filtering with neural re-ranking."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(recs_router)
    app.include_router(ratings_router)
    app.include_router(events_router)
    app.include_router(reviews_router)

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    def health():
        from api.model_registry import _engine
        return {
            "status":    "ok",
            "version":   settings.app_version,
            "model":     "loaded" if _engine is not None else "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Static Files ──────────────────────────────────────────────────────────
    os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", tags=["system"])
    def root():
        index_path = os.path.join("static", "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {
            "name":    settings.app_name,
            "version": settings.app_version,
            "docs":    "/docs",
            "message": "Frontend not generated yet."
        }

    return app

app = create_app()
