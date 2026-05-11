"""Base crawler class for all torrent/movie resource sites."""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from core.link_extractor import (
    extract_resolution_from_title,
    normalize_url,
    parse_size_string,
)
from core.models.schemas import ResourceType, SearchResult, SearchSource

logger = logging.getLogger(__name__)

# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class BaseCrawler(ABC):
    """Abstract base for site-specific crawlers."""

    def __init__(self, config: dict, proxy: Optional[str] = None):
        self.config = config
        self.base_url = config.get("base_url", "")
        self.proxy = proxy
        self.timeout = 15.0

    async def _get_client(self) -> httpx.AsyncClient:
        """Create an async HTTP client with proper headers."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        client_kwargs = {
            "headers": headers,
            "timeout": httpx.Timeout(self.timeout),
            "follow_redirects": True,
        }
        if self.proxy:
            client_kwargs["proxies"] = self.proxy
        return httpx.AsyncClient(**client_kwargs)

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return its HTML content."""
        try:
            async with await self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPError as e:
            logger.warning(f"[{self.__class__.__name__}] HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Unexpected error fetching {url}: {e}")
            return None

    def make_soup(self, html: str) -> BeautifulSoup:
        """Parse HTML into BeautifulSoup object."""
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Search for the given query on this site.

        Args:
            query: The movie name to search for.
            max_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects.
        """
        ...

    def _build_search_url(self, query: str) -> str:
        """Build the search URL using the configured search path."""
        search_path = self.config.get("search_path", "")
        encoded_query = query.replace(" ", "+")
        full_path = search_path.replace("{query}", encoded_query)
        return f"{self.base_url.rstrip('/')}{full_path}"

    async def check_link_validity(self, url: str) -> bool:
        """Quick HEAD request to check if a URL is still valid."""
        try:
            async with await self._get_client() as client:
                # For magnet links, we just assume they're valid
                if url.startswith("magnet:"):
                    return True
                resp = await client.head(url, timeout=5.0)
                return resp.status_code < 400
        except Exception:
            return False


class StaticCrawler(BaseCrawler):
    """Crawler for sites that serve static HTML content."""

    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Generic static HTML crawler using configured CSS selectors."""
        search_url = self._build_search_url(query)
        html = await self.fetch_page(search_url)
        if not html:
            return []

        soup = self.make_soup(html)
        selectors = self.config.get("selectors", {})
        results = []

        containers = soup.select(selectors.get("result_container", ""))
        if not containers:
            logger.info(f"[{self.__class__.__name__}] No results found for '{query}'")
            return results

        for container in containers[:max_results]:
            try:
                result = self._parse_container(container, selectors)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing result container: {e}")
                continue

        return results

    def _parse_container(self, container, selectors: dict) -> Optional[SearchResult]:
        """Parse a single search result container."""
        # Extract title
        title_el = container.select_one(selectors.get("title", "")) if selectors.get("title") else None
        if not title_el:
            return None
        title = title_el.get_text(strip=True)

        # Extract link
        link_el = container.select_one(selectors.get("link", "")) if selectors.get("link") else None
        if not link_el:
            return None
        raw_url = link_el.get("href", "")
        url = normalize_url(raw_url, self.base_url)

        # Determine resource type
        resource_type = ResourceType.MAGNET if url.startswith("magnet:") else ResourceType.TORRENT

        # Extract seeders
        seeders = None
        if selectors.get("seeders"):
            se_el = container.select_one(selectors["seeders"])
            if se_el:
                try:
                    seeders = int(se_el.get_text(strip=True))
                except (ValueError, TypeError):
                    seeders = None

        # Extract size
        size = None
        if selectors.get("size"):
            size_el = container.select_one(selectors["size"])
            if size_el:
                size_text = size_el.get_text(strip=True)
                size_bytes = parse_size_string(size_text)
                if size_bytes:
                    size = size_text

        resolution = extract_resolution_from_title(title)

        result = SearchResult(
            title=title,
            resource_type=resource_type,
            url=url,
            source=self._get_source(),
            size=size,
            seeders=seeders,
            resolution=resolution,
        )
        result.calculate_quality_score()
        return result

    def _get_source(self) -> SearchSource:
        """Map crawler name to SearchSource enum."""
        mapping = {
            "The Pirate Bay": SearchSource.PIRATE_BAY,
            "1337x": SearchSource.WEBSITE_1337X,
            "YTS": SearchSource.YTS,
            "BTDigg": SearchSource.BTDIGG,
            "RARBG (proxy)": SearchSource.RARBG,
        }
        return mapping.get(self.config.get("name", ""), SearchSource.OTHER)
