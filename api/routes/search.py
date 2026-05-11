"""Search API routes for CineSeeker."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.models.schemas import (
    ImageSearchRequest,
    ResourceType,
    SearchRequest,
    SearchResponse,
    SearchSource,
)
from core.search_engine import SearchOrchestrator
from core.services import MovieService, ResourceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

# Global orchestrator instance (initialized lazily)
_orchestrator: SearchOrchestrator = None


def get_orchestrator() -> SearchOrchestrator:
    """Get or create the search orchestrator singleton."""
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
    """Search for movie download resources by name.

    Supports multiple search strategies:
    - Google Dorking for direct file listings and magnet links
    - Site-specific crawlers (The Pirate Bay, 1337x, YTS, etc.)
    - Cached results with Redis (5 min) + PostgreSQL (30 min)
    """
    orchestrator = get_orchestrator()

    try:
        result = await orchestrator.search(
            q, max_results=max_results, session=session, skip_cache=refresh
        )
    except Exception as e:
        logger.exception(f"Search failed for query '{q}'")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    # Filter by source if specified
    if source:
        try:
            source_filter = SearchSource(source)
            result["results"] = [r for r in result["results"] if r["source"] == source_filter]
            result["total_count"] = len(result["results"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    # Persist results to database (if session available)
    if session and result.get("results"):
        try:
            # Create or update movie record
            movie = await MovieService.create_or_update(session, title=q)
            # Save resources
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
):
    """Search for movie resources using an image (screenshot/still).

    This endpoint will:
    1. Send the image to reverse image search (Yandex/Google)
    2. Extract movie metadata from the results
    3. Use the identified movie name to search for resources
    """
    # For Phase 1 MVP, return a placeholder
    # Phase 2 will implement the actual image recognition pipeline
    raise HTTPException(
        status_code=501,
        detail="Image search is not yet implemented. Phase 2 of the development plan.",
    )


@router.get("/sources")
async def list_sources():
    """List all available search sources."""
    return {
        "sources": [
            {"id": "google_dork", "name": "Google Dorking", "enabled": True},
            {"id": "the_pirate_bay", "name": "The Pirate Bay", "enabled": True},
            {"id": "1337x", "name": "1337x", "enabled": True},
            {"id": "yts", "name": "YTS", "enabled": True},
            {"id": "btdigg", "name": "BTDigg", "enabled": True},
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "CineSeeker"}
