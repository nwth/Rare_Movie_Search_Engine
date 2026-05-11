"""Database CRUD service layer for CineSeeker."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.db_models import Movie, Resource, SearchCache
from core.models.schemas import SearchResult, SearchSource

logger = logging.getLogger(__name__)


class MovieService:
    """CRUD operations for Movie metadata."""

    @staticmethod
    async def get_by_imdb(session: AsyncSession, imdb_id: str) -> Optional[Movie]:
        """Find a movie by its IMDb ID."""
        result = await session.execute(select(Movie).where(Movie.imdb_id == imdb_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_title_and_year(
        session: AsyncSession, title: str, year: Optional[int] = None
    ) -> Optional[Movie]:
        """Find a movie by title (and optionally year)."""
        query = select(Movie).where(Movie.title.ilike(f"%{title}%"))
        if year:
            query = query.where(Movie.year == year)
        result = await session.execute(query.order_by(Movie.search_count.desc()))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_or_update(
        session: AsyncSession, title: str, year: Optional[int] = None,
        original_title: Optional[str] = None, imdb_id: Optional[str] = None,
        poster_url: Optional[str] = None, overview: Optional[str] = None,
    ) -> Movie:
        """Create a new movie or update search count if exists."""
        # Try to find existing
        existing = None
        if imdb_id:
            existing = await MovieService.get_by_imdb(session, imdb_id)
        if not existing:
            existing = await MovieService.get_by_title_and_year(session, title, year)

        if existing:
            existing.search_count += 1
            existing.last_searched_at = datetime.now(timezone.utc)
            if poster_url and not existing.poster_url:
                existing.poster_url = poster_url
            if overview and not existing.overview:
                existing.overview = overview
            movie = existing
        else:
            movie = Movie(
                title=title,
                original_title=original_title,
                year=year,
                imdb_id=imdb_id,
                poster_url=poster_url,
                overview=overview,
                search_count=1,
                last_searched_at=datetime.now(timezone.utc),
            )
            session.add(movie)

        await session.commit()
        await session.refresh(movie)
        return movie

    @staticmethod
    async def get_top_searched(
        session: AsyncSession, limit: int = 20
    ) -> list[Movie]:
        """Get most searched movies."""
        result = await session.execute(
            select(Movie).order_by(Movie.search_count.desc()).limit(limit)
        )
        return list(result.scalars().all())


class ResourceService:
    """CRUD operations for download Resources."""

    @staticmethod
    async def get_by_info_hash(
        session: AsyncSession, info_hash: str
    ) -> Optional[Resource]:
        """Find a resource by its magnet InfoHash."""
        result = await session.execute(
            select(Resource).where(Resource.info_hash == info_hash)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_movie_id(
        session: AsyncSession, movie_id: int
    ) -> list[Resource]:
        """Get all resources for a movie."""
        result = await session.execute(
            select(Resource)
            .where(Resource.movie_id == movie_id)
            .order_by(Resource.quality_score.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def bulk_save(
        session: AsyncSession, movie_id: int, results: list[SearchResult]
    ) -> int:
        """Save multiple search results for a movie. Returns count of new saves."""
        count = 0
        for r in results:
            # Skip if already exists by info_hash
            if r.info_hash:
                existing = await ResourceService.get_by_info_hash(session, r.info_hash)
                if existing:
                    continue

            resource = Resource(
                movie_id=movie_id,
                title=r.title,
                url=r.url,
                resource_type=r.resource_type.value,
                info_hash=r.info_hash,
                source=r.source.value,
                size=r.size,
                seeders=r.seeders,
                leechers=r.leechers,
                resolution=r.resolution,
                quality_score=r.quality_score,
                is_valid=r.is_valid,
            )
            session.add(resource)
            count += 1

        if count > 0:
            await session.commit()
        return count

    @staticmethod
    async def mark_invalid(
        session: AsyncSession, resource_id: int
    ) -> None:
        """Mark a resource as invalid (dead link)."""
        await session.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        result = await session.get(Resource, resource_id)
        if result:
            result.is_valid = False
            result.last_checked_at = datetime.now(timezone.utc)
            await session.commit()

    @staticmethod
    async def clean_old_resources(
        session: AsyncSession, days: int = 90
    ) -> int:
        """Delete resources not checked in N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await session.execute(
            delete(Resource).where(
                Resource.last_checked_at < cutoff,
                Resource.is_valid == False,  # noqa: E712
            )
        )
        await session.commit()
        return result.rowcount


class CacheService:
    """Search cache service (database-backed for persistence)."""

    CACHE_TTL_MINUTES = 30

    @staticmethod
    async def get(session: AsyncSession, query: str) -> Optional[dict]:
        """Get cached search result for a query if not expired."""
        result = await session.execute(
            select(SearchCache).where(
                SearchCache.query == query.lower().strip(),
                SearchCache.expires_at > datetime.now(timezone.utc),
            )
        )
        cache = result.scalar_one_or_none()
        if cache:
            logger.debug(f"Cache hit for query: '{query}'")
            return {
                "results": json.loads(cache.result_json),
                "total_count": cache.total_count,
                "search_time_ms": cache.search_time_ms,
                "sources_used": json.loads(cache.sources_used or "[]"),
            }
        return None

    @staticmethod
    async def set(
        session: AsyncSession,
        query: str,
        results: list[dict],
        total_count: int,
        search_time_ms: int,
        sources_used: list[str],
    ) -> None:
        """Cache a search result."""
        # Remove old cache entry if exists
        await session.execute(
            delete(SearchCache).where(SearchCache.query == query.lower().strip())
        )

        cache = SearchCache(
            query=query.lower().strip(),
            result_json=json.dumps(results, ensure_ascii=False, default=str),
            total_count=total_count,
            sources_used=json.dumps(sources_used, ensure_ascii=False),
            search_time_ms=search_time_ms,
            expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=CacheService.CACHE_TTL_MINUTES
            ),
        )
        session.add(cache)
        await session.commit()
        logger.debug(f"Cached search result for '{query}' ({CacheService.CACHE_TTL_MINUTES}min TTL)")
