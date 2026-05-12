"""Movie metadata enrichment service (TMDb, OMDb, Douban).

Takes raw movie names from image search and enriches them with
standardized metadata (IMDb ID, poster, directors, etc.).
"""

import logging
from typing import Optional

import httpx

from config.config import settings
from core.models.schemas import MovieMetadata

logger = logging.getLogger(__name__)


class TMDBClient:
    """The Movie Database (TMDb) API wrapper.

    Free tier: https://www.themoviedb.org/signup
    No credit card required, 40 queries per 10 seconds.
    """

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.tmdb_api_key
        if not self.api_key:
            # Use a demo key for basic lookups
            self.api_key = None

    async def search_movie(
        self, title: str, year: Optional[int] = None
    ) -> Optional[MovieMetadata]:
        """Search for a movie by title and year."""
        if not self.api_key:
            logger.warning("TMDb API key not configured (set TMDB_API_KEY in .env)")
            return None

        params = {
            "api_key": self.api_key,
            "query": title,
            "language": "en-US",
        }
        if year:
            params["year"] = year

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            base_url=self.BASE_URL,
        ) as client:
            try:
                resp = await client.get("/search/movie", params=params)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_search_result(data)
            except Exception as e:
                logger.debug(f"TMDb search failed for '{title}': {e}")
                return None

    async def get_by_imdb(self, imdb_id: str) -> Optional[MovieMetadata]:
        """Look up a movie by its IMDb ID."""
        if not self.api_key:
            return None

        params = {
            "api_key": self.api_key,
            "external_source": "imdb_id",
            "language": "en-US",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            base_url=self.BASE_URL,
        ) as client:
            try:
                resp = await client.get(
                    f"/find/{imdb_id}", params=params
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("movie_results", [])
                if not results:
                    return None

                movie = results[0]
                return MovieMetadata(
                    title=movie.get("title", ""),
                    year=int(movie.get("release_date", "0000")[:4])
                        if movie.get("release_date") else None,
                    original_title=movie.get("original_title"),
                    directors=[],  # Directors need a separate credits call
                    imdb_id=imdb_id,
                    tmdb_id=movie.get("id"),
                    poster_url=(
                        f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                        if movie.get("poster_path") else None
                    ),
                    overview=movie.get("overview"),
                )
            except Exception as e:
                logger.debug(f"TMDb IMDb lookup failed for '{imdb_id}': {e}")
                return None

    async def enrich_metadata(self, meta: MovieMetadata) -> MovieMetadata:
        """Enrich partial metadata with TMDb data."""
        if not self.api_key or not meta.title:
            return meta

        tmdb_meta = None

        # Try by IMDb ID first
        if meta.imdb_id:
            tmdb_meta = await self.get_by_imdb(meta.imdb_id)

        # Fall back to title search
        if not tmdb_meta:
            tmdb_meta = await self.search_movie(meta.title, meta.year)

        if not tmdb_meta:
            return meta

        # Merge, keeping original values when TMDb doesn't have them
        return MovieMetadata(
            title=tmdb_meta.title or meta.title,
            year=tmdb_meta.year or meta.year,
            original_title=tmdb_meta.original_title or meta.original_title,
            directors=tmdb_meta.directors or meta.directors,
            imdb_id=tmdb_meta.imdb_id or meta.imdb_id,
            tmdb_id=tmdb_meta.tmdb_id or meta.tmdb_id,
            poster_url=tmdb_meta.poster_url or meta.poster_url,
            overview=tmdb_meta.overview or meta.overview,
        )

    def _parse_search_result(self, data: dict) -> Optional[MovieMetadata]:
        """Parse TMDb search response."""
        results = data.get("results", [])
        if not results:
            return None

        movie = results[0]
        return MovieMetadata(
            title=movie.get("title", ""),
            year=int(movie.get("release_date", "0000")[:4])
                if movie.get("release_date") else None,
            original_title=movie.get("original_title"),
            directors=[],
            imdb_id=movie.get("imdb_id"),
            tmdb_id=movie.get("id"),
            poster_url=(
                f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                if movie.get("poster_path") else None
            ),
            overview=movie.get("overview"),
        )


class OMDbClient:
    """OMDb API wrapper (alternative to TMDb for IMDb data)."""

    BASE_URL = "https://www.omdbapi.com"

    async def search(self, title: str, year: Optional[int] = None) -> Optional[dict]:
        """Search OMDb for a movie."""
        api_key = settings.omdb_api_key
        if not api_key:
            return None

        params = {
            "apikey": api_key,
            "t": title,
            "plot": "short",
        }
        if year:
            params["y"] = year

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
        ) as client:
            try:
                resp = await client.get(self.BASE_URL, params=params)
                data = resp.json()
                if data.get("Response") == "True":
                    return data
            except Exception as e:
                logger.debug(f"OMDb search failed: {e}")
        return None


class MetadataOrchestrator:
    """Coordinates multiple metadata sources for best coverage."""

    def __init__(self):
        self.tmdb = TMDBClient()
        self.omdb = OMDbClient()

    async def enrich(self, meta: MovieMetadata) -> MovieMetadata:
        """Enrich movie metadata using all available sources."""
        enriched = await self.tmdb.enrich_metadata(meta)

        # If TMDb didn't give us an IMDb ID, try OMDb
        if not enriched.imdb_id:
            omdb_data = await self.omdb.search(enriched.title, enriched.year)
            if omdb_data:
                enriched.imdb_id = omdb_data.get("imdbID")
                if not enriched.poster_url:
                    enriched.poster_url = omdb_data.get("Poster")
                if not enriched.directors:
                    director = omdb_data.get("Director", "")
                    enriched.directors = [d.strip() for d in director.split(",") if d.strip()]

        logger.info(
            f"Enriched metadata: '{meta.title}' → "
            f"'{enriched.title}' ({enriched.year}) "
            f"[IMDb: {enriched.imdb_id}]"
        )
        return enriched
