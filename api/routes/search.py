"""Search API routes for CineSeeker."""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import settings
from core.database import get_session
from core.image_search import ImageSearchOrchestrator
from core.metadata import MetadataOrchestrator
from core.models.schemas import (
    MovieMetadata,
    SearchResponse,
    SearchSource,
)
from core.search_engine import SearchOrchestrator
from core.services import MovieService, ResourceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

_orchestrator: SearchOrchestrator = None


def get_orchestrator() -> SearchOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SearchOrchestrator()
    return _orchestrator


@router.get("/search", response_model=SearchResponse)
async def search_movie(
    q: str = Query(..., min_length=1, max_length=200, description="Movie name or keywords"),
    max_results: int = Query(default=30, ge=1, le=100, description="Maximum results to return"),
    source: str = Query(default=None, description="Filter by source (e.g., google_dork, the_pirate_bay)"),
    refresh: bool = Query(default=False, description="Skip cache and force fresh search"),
    session: AsyncSession = Depends(get_session),
):
    """Search for movie download resources by name."""
    orchestrator = get_orchestrator()
    try:
        result = await orchestrator.search(
            q, max_results=max_results, session=session, skip_cache=refresh
        )
    except Exception as e:
        logger.exception(f"Search failed for query '{q}'")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    if source:
        try:
            source_filter = SearchSource(source)
            result["results"] = [r for r in result["results"] if r["source"] == source_filter]
            result["total_count"] = len(result["results"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    if session and result.get("results"):
        try:
            movie = await MovieService.create_or_update(session, title=q)
            from core.models.schemas import SearchResult as SearchResultSchema
            saved = await ResourceService.bulk_save(
                session, movie.id,
                [SearchResultSchema(**r) for r in result["results"]]
            )
            if saved:
                logger.debug(f"Saved {saved} new resources for '{q}'")
        except Exception as e:
            logger.debug(f"Failed to persist search results: {e}")

    return SearchResponse(
        query=q,
        results=result["results"],
        total_count=result["total_count"],
        search_time_ms=result["search_time_ms"],
        sources_used=result["sources_used"],
    )


@router.get("/search/image")
async def search_by_image(
    image_url: str = Query(..., description="URL of the movie screenshot/still to search by"),
    max_results: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Search for movie resources using an image URL.

    Pipeline: image → Yandex/SerpApi → movie metadata → resource search
    """
    image_orc = ImageSearchOrchestrator()
    movie_meta = await image_orc.identify_movie(image_url)

    if not movie_meta:
        raise HTTPException(
            status_code=404,
            detail="Could not identify any movie from this image.",
        )

    try:
        meta_orc = MetadataOrchestrator()
        movie_meta = await meta_orc.enrich(movie_meta)
    except Exception as e:
        logger.debug(f"Metadata enrichment failed: {e}")

    query = movie_meta.title
    if movie_meta.year:
        query = f"{movie_meta.title} {movie_meta.year}"

    search_orc = get_orchestrator()
    try:
        search_result = await search_orc.search(query, max_results=max_results, session=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resource search failed: {e}")

    if session:
        try:
            await MovieService.create_or_update(
                session, title=movie_meta.title, year=movie_meta.year,
                original_title=movie_meta.original_title, imdb_id=movie_meta.imdb_id,
                poster_url=movie_meta.poster_url, overview=movie_meta.overview,
            )
        except Exception as e:
            logger.debug(f"Failed to persist movie: {e}")

    return SearchResponse(
        query=query, movie=movie_meta,
        results=search_result["results"],
        total_count=search_result["total_count"],
        search_time_ms=search_result["search_time_ms"],
        sources_used=search_result["sources_used"],
    )


@router.post("/search/image/upload")
async def search_by_image_upload(
    file: UploadFile = File(..., description="Movie screenshot or still image (JPEG/PNG/WebP, max 10MB)"),
    max_results: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Search for movie resources by uploading an image file.

    Pipeline: upload → base64 → SerpApi Google Lens → metadata → resource search
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", None):
        raise HTTPException(status_code=400, detail="Unsupported format. Use JPEG, PNG or WebP.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 10MB.")

    ext = (file.filename or "").split(".")[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")
    data_uri = f"data:{mime};base64,{base64.b64encode(contents).decode()}"

    image_orc = ImageSearchOrchestrator()
    movie_meta = await image_orc.identify_movie(data_uri)

    if not movie_meta:
        raise HTTPException(status_code=404, detail="Could not identify any movie from this image.")

    try:
        meta_orc = MetadataOrchestrator()
        movie_meta = await meta_orc.enrich(movie_meta)
    except Exception as e:
        logger.debug(f"Metadata enrichment failed: {e}")

    query = movie_meta.title
    if movie_meta.year:
        query = f"{movie_meta.title} {movie_meta.year}"

    search_orc = get_orchestrator()
    search_result = await search_orc.search(query, max_results=max_results, session=session)

    return SearchResponse(
        query=query, movie=movie_meta,
        results=search_result["results"],
        total_count=search_result["total_count"],
        search_time_ms=search_result["search_time_ms"],
        sources_used=search_result["sources_used"],
    )


@router.get("/sources")
async def list_sources():
    """List all available search sources."""
    return {
        "sources": [
            {"id": "google_dork", "name": "Google Dorking", "type": "text", "enabled": True},
            {"id": "the_pirate_bay", "name": "The Pirate Bay", "type": "torrent", "enabled": True},
            {"id": "1337x", "name": "1337x", "type": "torrent", "enabled": True},
            {"id": "yts", "name": "YTS", "type": "torrent", "enabled": True},
            {"id": "btdigg", "name": "BTDigg", "type": "torrent", "enabled": True},
            {"id": "quark_pan", "name": "夸克网盘", "type": "cloud_drive", "enabled": True},
            {"id": "aliyun_drive", "name": "阿里云盘", "type": "cloud_drive", "enabled": True},
            {"id": "baidu_pan", "name": "百度网盘", "type": "cloud_drive", "enabled": True},
            {"id": "123_pan", "name": "123云盘", "type": "cloud_drive", "enabled": True},
            {"id": "yandex_image", "name": "Yandex 图片识别", "type": "image", "enabled": True},
            {"id": "serpapi_lens", "name": "Google Lens (SerpApi)", "type": "image", "enabled": bool(settings.serpapi_key)},
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "CineSeeker"}
