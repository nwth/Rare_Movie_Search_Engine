"""Reverse image search service for CineSeeker.

Extracts movie metadata (title, year) from screenshots/stills
using Yandex Reverse Image Search, Google Lens, or SerpApi.
"""

import asyncio
import json
import logging
import re
from typing import Optional
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup

from config.config import settings
from core.crawlers.base import USER_AGENTS
from core.models.schemas import MovieMetadata

logger = logging.getLogger(__name__)


def _clean_title(raw: str) -> str:
    """Clean extracted title string."""
    # Remove common noise
    noise_patterns = [
        r"\b\d{3,4}p\b", r"\bblu-?ray\b", r"\bweb-?dl\b", r"\bhdtv\b",
        r"\bhdrip\b", r"\bbc\b", r"\benglish\b", r"\bsub\w*\b",
        r"[-–—|]", r"\s+",
    ]
    for p in noise_patterns:
        raw = re.sub(p, " ", raw, flags=re.IGNORECASE)
    return raw.strip()


def _extract_year(text: str) -> Optional[int]:
    """Extract a 4-digit year from text (1900-2029)."""
    match = re.search(r"\b(19[0-9]{2}|20[0-2][0-9])\b", text)
    if match:
        return int(match.group(0))
    return None


class YandexImageSearch:
    """Reverse image search via Yandex Images (free, no API key needed)."""

    BASE_URL = "https://yandex.com/images/search"

    async def search_by_url(self, image_url: str) -> list[MovieMetadata]:
        """Search Yandex by image URL and extract movie candidates."""
        params = {
            "rpt": "imageview",
            "url": image_url,
            "format": "json",
        }
        search_url = f"{self.BASE_URL}?{urlencode(params)}"

        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            try:
                resp = await client.get(search_url)
                resp.raise_for_status()
                return self._parse_response(resp.text)
            except Exception as e:
                logger.warning(f"Yandex search failed: {e}")
                return []

    def _parse_response(self, html: str) -> list[MovieMetadata]:
        """Parse Yandex image search results to extract movie info."""
        soup = BeautifulSoup(html, "lxml")
        candidates = []

        # Yandex shows "similar images" with tags/titles
        # Extract from page title and meta description
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            candidates.extend(self._parse_text_for_movies(title_text))

        # Extract from search result tags
        for tag in soup.select("a.tag, div.CbirItemView"):
            tag_text = tag.get_text(strip=True)
            candidates.extend(self._parse_text_for_movies(tag_text))

        # Look at link descriptions
        for link in soup.select("a.link, a.Link"):
            link_text = link.get_text(strip=True)
            candidates.extend(self._parse_text_for_movies(link_text))

        # Deduplicate by title
        seen = set()
        unique = []
        for m in candidates:
            key = f"{m.title}_{m.year}".lower()
            if key not in seen:
                seen.add(key)
                unique.append(m)

        return unique[:5]

    def _parse_text_for_movies(self, text: str) -> list[MovieMetadata]:
        """Try to extract movie title and year from text snippets."""
        movies = []
        if not text or len(text) < 3:
            return movies

        year = _extract_year(text)
        title = _clean_title(text)

        if title and len(title) > 2:
            movies.append(MovieMetadata(
                title=title,
                year=year,
            ))

        return movies


class SerpApiImageSearch:
    """Reverse image search via SerpApi (requires API key)."""

    BASE_URL = "https://serpapi.com/search"

    async def search_by_url(self, image_url: str) -> list[MovieMetadata]:
        """Search via SerpApi Google Lens endpoint."""
        api_key = settings.serpapi_key
        if not api_key:
            logger.warning("SerpApi key not configured")
            return []

        params = {
            "api_key": api_key,
            "engine": "google_lens",
            "url": image_url,
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
        ) as client:
            try:
                resp = await client.get(self.BASE_URL, params=params)
                data = resp.json()

                if "error" in data:
                    logger.error(f"SerpApi error: {data['error']}")
                    return []

                return self._parse_response(data)

            except Exception as e:
                logger.warning(f"SerpApi search failed: {e}")
                return []

    def _parse_response(self, data: dict) -> list[MovieMetadata]:
        """Parse SerpApi JSON response into movie metadata."""
        candidates = []

        # Extract from visual matches
        for match in data.get("visual_matches", []):
            title = match.get("title", "")
            source = match.get("source", "")
            text = f"{title} {source}"
            year = _extract_year(text)
            clean = _clean_title(title)

            if clean:
                candidates.append(MovieMetadata(
                    title=clean,
                    year=year,
                ))

        # Extract from search result knowledge graph
        kg = data.get("knowledge_graph", {})
        if kg:
            title = kg.get("title", "") or kg.get("name", "")
            year = _extract_year(str(kg))
            if title:
                candidates.append(MovieMetadata(
                    title=_clean_title(title),
                    year=year,
                    description=kg.get("description"),
                ))

        return candidates[:5]


class ImageSearchOrchestrator:
    """Orchestrates multiple image search engines for best results."""

    def __init__(self):
        self.yandex = YandexImageSearch()
        self.serpapi = SerpApiImageSearch()

    async def identify_movie(self, image_url: str) -> Optional[MovieMetadata]:
        """Try to identify a movie from an image URL.

        Strategy:
        1. Try SerpApi (Google Lens) first if configured
        2. Fall back to Yandex free search
        3. Return the best candidate
        """
        candidates = []

        # Try SerpApi (best accuracy)
        if settings.serpapi_key:
            try:
                serp_results = await self.serpapi.search_by_url(image_url)
                candidates.extend(serp_results)
            except Exception as e:
                logger.debug(f"SerpApi failed: {e}")

        # Try Yandex (free, good for movie stills)
        if not candidates:
            try:
                yandex_results = await self.yandex.search_by_url(image_url)
                candidates.extend(yandex_results)
            except Exception as e:
                logger.debug(f"Yandex failed: {e}")

        if not candidates:
            return None

        # Return the best candidate (prioritize results with year)
        with_year = [c for c in candidates if c.year]
        if with_year:
            return with_year[0]
        return candidates[0]

    async def search_resources_from_image(
        self, image_url: str, max_results: int = 30
    ) -> dict:
        """Full pipeline: image → movie metadata → resource search.

        Returns dict with 'movie' metadata and 'search_result' from orchestrator.
        """
        from core.search_engine import SearchOrchestrator
        from core.services import MovieService
        from core.database import get_session_maker

        # Step 1: Identify movie from image
        movie_meta = await self.identify_movie(image_url)
        if not movie_meta:
            return {
                "movie": None,
                "error": "Could not identify movie from this image",
                "results": [],
                "total_count": 0,
                "search_time_ms": 0,
                "sources_used": [],
            }

        # Step 2: Build search query
        query = movie_meta.title
        if movie_meta.year:
            query = f"{movie_meta.title} {movie_meta.year}"

        # Step 3: Search for resources
        orchestrator = SearchOrchestrator()
        search_result = await orchestrator.search(query, max_results=max_results)

        # Step 4: Try to persist movie metadata
        session_maker = get_session_maker()
        if session_maker:
            async with session_maker() as session:
                try:
                    await MovieService.create_or_update(
                        session,
                        title=movie_meta.title,
                        year=movie_meta.year,
                        original_title=movie_meta.original_title,
                        overview=movie_meta.overview,
                    )
                except Exception as e:
                    logger.debug(f"Failed to persist movie metadata: {e}")

        return {
            "movie": movie_meta.model_dump(),
            **search_result,
        }
