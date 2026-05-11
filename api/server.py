"""FastAPI application factory for CineSeeker."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info(f"CineSeeker starting up on {settings.host}:{settings.port}")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("CineSeeker shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CineSeeker - Rare Movie Search Engine",
        description=(
            "A vertical search engine for rare movies. "
            "Supports text and image-based search, aggregating results "
            "from torrent sites, cloud drives, and Google Dorking."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    from api.routes.search import router as search_router
    app.include_router(search_router)

    # Serve frontend static files
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
