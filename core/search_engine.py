"""Search engine orchestrator for CineSeeker.

Combines Google Dorking, site-specific crawlers, and result aggregation.
"""

import asyncio
import logging
import random
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config.config import settings
from core.crawlers.base import USER_AGENTS
from core.crawlers.torrent_sites import (
    PirateBayCrawler,
    YTSCrawler,
    _1337xCrawler,
)
from core.link_extractor import (
    extract_info_hash,
    extract_links_from_html,
    extract_resolution_from_title,
)
from core.models.schemas import (
    ResourceType,
    SearchResult,
    SearchSource,
)

logger = logging.getLogger(__name__)


class GoogleDorkEngine:
    """Perform Google Dorking searches to find magnet/torrent resources."""

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.dork_queries = settings.get_google_dork_queries()
        self.timeout = settings.google_dork_timeout

    async def _get_client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        client_kwargs = {
            "headers": headers,
            "timeout": httpx.Timeout(self.timeout),
            "follow_redirects": True,
        }
        if self.proxy:
            client_kwargs["proxies"] = self.proxy
        return httpx.AsyncClient(**client_kwargs)

    async def search(self, query: str, max_results: int = 30) -> list[SearchResult]:
        """Run all configured Google Dork queries concurrently."""
        tasks = []
        for dork in self.dork_queries:
            if not dork.get("enabled", True):
                continue
            dork_query = dork["query"].replace("{query}", query)
            tasks.append(self._execute_dork(dork_query, dork.get("weight", 1.0)))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[SearchResult] = []
        seen_hashes = set()

        for results in all_results:
            if isinstance(results, Exception):
                logger.warning(f"Dork query failed: {results}")
                continue
            for result in results:
                # Deduplicate by info_hash or URL
                dedup_key = result.info_hash or result.url
                if dedup_key and dedup_key not in seen_hashes:
                    seen_hashes.add(dedup_key)
                    merged.append(result)

        # Sort by quality score descending
        merged.sort(key=lambda r: r.quality_score, reverse=True)
        return merged[:max_results]

    async def _execute_dork(self, dork_query: str, weight: float = 1.0) -> list[SearchResult]:
        """Execute a single Google Dork query and parse results."""
        search_url = f"https://www.google.com/search?q={dork_query.replace(' ', '+')}&num=20"
        results = []

        async with await self._get_client() as client:
            try:
                resp = await client.get(search_url)
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                logger.debug(f"Google Dork request failed: {dork_query[:50]}... - {e}")
                return results

        # Extract links from HTML
        soup = BeautifulSoup(html, "lxml")
        extracted = extract_links_from_html(html)

        # Also look for magnet/torrent links in search result snippets
        for link_data in extracted:
            title = self._find_result_title(soup, link_data["url"]) or link_data["url"]
            resolution = extract_resolution_from_title(title)
            info_hash = link_data.get("info_hash")

            result = SearchResult(
                title=title,
                resource_type=link_data["type"],
                url=link_data["url"],
                info_hash=info_hash,
                source=SearchSource.GOOGLE_DORK,
                resolution=resolution,
            )
            # Apply dork weight to quality score
            result.quality_score = weight * 2.0
            results.append(result)

        return results

    def _find_result_title(self, soup: BeautifulSoup, target_url: str) -> Optional[str]:
        """Try to find the title of a search result containing the target URL."""
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if target_url in href:
                return link.get_text(strip=True) or None
        return None


class CrawlerManager:
    """Manages all site-specific crawlers and aggregates their results."""

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self._init_crawlers()

    def _init_crawlers(self):
        """Initialize crawlers from config."""
        site_configs = settings.get_crawler_sites()
        self.crawlers = []

        for site_cfg in site_configs:
            if not site_cfg.get("enabled", False):
                continue
            name = site_cfg.get("name", "")
            if name == "The Pirate Bay":
                self.crawlers.append(PirateBayCrawler(site_cfg, self.proxy))
            elif name == "1337x":
                self.crawlers.append(_1337xCrawler(site_cfg, self.proxy))
            elif name == "YTS":
                self.crawlers.append(YTSCrawler(site_cfg, self.proxy))
            elif name == "BTDigg":
                from core.crawlers.base import StaticCrawler
                self.crawlers.append(StaticCrawler(site_cfg, self.proxy))
            else:
                from core.crawlers.base import StaticCrawler
                self.crawlers.append(StaticCrawler(site_cfg, self.proxy))

    async def search_all(self, query: str, max_results: int = 30) -> list[SearchResult]:
        """Run all crawlers concurrently and merge results."""
        tasks = [crawler.search(query, max_results) for crawler in self.crawlers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[SearchResult] = []
        seen = set()

        for results in all_results:
            if isinstance(results, Exception):
                logger.warning(f"Crawler failed: {results}")
                continue
            for result in results:
                dedup_key = result.info_hash or result.url
                if dedup_key and dedup_key not in seen:
                    seen.add(dedup_key)
                    merged.append(result)

        merged.sort(key=lambda r: r.quality_score, reverse=True)
        return merged[:max_results]


class SearchOrchestrator:
    """Top-level orchestrator coordinating all search strategies."""

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.dork_engine = GoogleDorkEngine(proxy)
        self.crawler_manager = CrawlerManager(proxy)

    async def search(self, query: str, max_results: int = 30) -> dict:
        """Execute a full multi-source search.

        Returns:
            Dict with 'results', 'sources_used', and 'search_time_ms'.
        """
        start_time = time.time()

        # Run both search strategies concurrently
        dork_task = self.dork_engine.search(query, max_results)
        crawler_task = self.crawler_manager.search_all(query, max_results)

        dork_results, crawler_results = await asyncio.gather(dork_task, crawler_task)

        # Merge and deduplicate
        all_results = dork_results + crawler_results
        seen = set()
        unique_results: list[SearchResult] = []
        for r in sorted(all_results, key=lambda x: x.quality_score, reverse=True):
            key = r.info_hash or r.url
            if key and key not in seen:
                seen.add(key)
                unique_results.append(r)

        sources_used = list(set(r.source for r in unique_results))
        search_time = int((time.time() - start_time) * 1000)

        return {
            "results": unique_results[:max_results],
            "sources_used": sources_used,
            "search_time_ms": search_time,
            "total_count": len(unique_results[:max_results]),
        }
