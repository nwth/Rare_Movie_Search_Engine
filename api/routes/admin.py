"""Admin / monitoring API routes for CineSeeker."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.models.db_models import Movie, Resource, SearchCache
from core.cache import RedisCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Get database statistics."""
    from sqlalchemy import select, func

    stats = {}

    if session:
        # Movie count
        result = await session.execute(select(func.count(Movie.id)))
        stats["movies_total"] = result.scalar()

        # Resource count
        result = await session.execute(select(func.count(Resource.id)))
        stats["resources_total"] = result.scalar()

        # Resource by type
        result = await session.execute(
            select(Resource.resource_type, func.count(Resource.id))
            .group_by(Resource.resource_type)
        )
        stats["resources_by_type"] = {row[0]: row[1] for row in result}

        # Cache entries
        result = await session.execute(select(func.count(SearchCache.id)))
        stats["cache_entries"] = result.scalar()

        # Top searched movies
        result = await session.execute(
            select(Movie.title, Movie.year, Movie.search_count)
            .order_by(Movie.search_count.desc())
            .limit(10)
        )
        stats["top_searched"] = [
            {"title": row[0], "year": row[1], "searches": row[2]}
            for row in result
        ]

    stats["version"] = "0.3.0"
    return stats


@router.post("/cache/clear")
async def clear_cache():
    """Clear the Redis search cache."""
    await RedisCache.clear_all()
    return {"status": "ok", "message": "Cache cleared"}


@router.get("/health/full")
async def full_health_check(session: AsyncSession = Depends(get_session)):
    """Full health check with database status."""
    checks = {
        "api": "ok",
        "database": "disconnected",
        "redis": "disconnected",
    }

    # Check DB
    if session:
        try:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"

    # Check Redis
    try:
        from core.cache import get_redis
        client = get_redis()
        if client:
            await client.ping()
            checks["redis"] = "ok"
    except Exception:
        pass

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "version": "0.3.0",
    }
