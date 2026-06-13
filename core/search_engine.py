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
from core.crawlers.cloud_drives import PanDorkCrawler
from core.crawlers.dynamic import DynamicCrawlerManager, CRAWLER_CONFIGS
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
        """Initialize crawlers from config + cloud drive dork crawlers."""
        site_configs = settings.get_crawler_sites()
        self.crawlers = []

        # Site-specific crawlers from config.yaml
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

        # Cloud drive crawlers (from config.yaml dork queries)
        self._init_cloud_drive_crawlers()

    def _init_cloud_drive_crawlers(self):
        """Create cloud-drive-specific dork crawlers."""
        drive_configs = [
            ("QuarkPan", 'site:pan.quark.cn {query}', ResourceType.CLOUD_DRIVE, 1.0),
            ("AliYunDrive", 'site:aliyundrive.com {query}', ResourceType.CLOUD_DRIVE, 0.9),
            ("BaiduPan", 'site:pan.baidu.com {query} 提取码', ResourceType.CLOUD_DRIVE, 0.8),
            ("123Pan", 'site:123pan.com {query}', ResourceType.CLOUD_DRIVE, 0.7),
        ]
        for name, dork, rtype, weight in drive_configs:
            self.crawlers.append(
                PanDorkCrawler(name, dork, rtype, weight, self.proxy)
            )

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
    """Top-level orchestrator coordinating all search strategies.

    Search layers (run concurrently):
    1. Google Dorking (8+ dork queries)
    2. Static crawlers (TPB, 1337x, YTS, BTDigg)
    3. Cloud drive dork crawlers (Quark, AliYun, Baidu, 123Pan)
    4. Dynamic/JS crawlers (TorrentGalaxy, LimeTorrents, Nyaa.si)
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.dork_engine = GoogleDorkEngine(proxy)
        self.crawler_manager = CrawlerManager(proxy)
        self.dynamic_crawler = DynamicCrawlerManager()

    async def search(
        self, query: str, max_results: int = 30,
        session=None, skip_cache: bool = False,
        use_dynamic: bool = False
    ) -> dict:
        """Execute a full multi-source search with caching.

        Caching flow:
        1. Redis (fast, 5 min TTL) → return if hit
        2. PostgreSQL DB cache (30 min TTL) → return if hit
        3. Actual search → populate both caches

        Post-processing:
        - Cloud drive links: auto-extract 提取码
        - Low results (<5): add streaming fallback

        Returns:
            Dict with 'results', 'sources_used', 'search_time_ms', 'total_count'.
        """
        # Try cache first (unless skip_cache)
        if not skip_cache:
            cached = await self._try_cache(query, session)
            if cached:
                return cached

        # No cache hit — do the actual search
        start_time = time.time()

        dork_task = self.dork_engine.search(query, max_results)
        crawler_task = self.crawler_manager.search_all(query, max_results)

        if use_dynamic:
            # Also run Playwright dynamic crawlers (slower but more thorough)
            dynamic_task = self.dynamic_crawler.search_all(query, max_results)
            dork_results, crawler_results, dynamic_results = await asyncio.gather(
                dork_task, crawler_task, dynamic_task
            )
        else:
            dynamic_results = []
            dork_results, crawler_results = await asyncio.gather(dork_task, crawler_task)

        # Merge and deduplicate
        all_results = dork_results + crawler_results + dynamic_results
        seen = set()
        unique_results: list[SearchResult] = []
        for r in sorted(all_results, key=lambda x: x.quality_score, reverse=True):
            key = r.info_hash or r.url
            if key and key not in seen:
                seen.add(key)
                unique_results.append(r)

        sources_used = list(set(r.source for r in unique_results))
        search_time = int((time.time() - start_time) * 1000)
        final_results = unique_results[:max_results]

        # Post-processing: extract 提取码 for cloud drive links
        asyncio.ensure_future(self._enrich_cloud_links(final_results))

        # Post-processing: streaming fallback if few download results
        if len(final_results) < 5:
            try:
                from core.stream_parser import StreamingFallback
                stream_results = await StreamingFallback.find_streaming(query, max_results=5)
                existing_urls = {r.url for r in final_results}
                for sr in stream_results:
                    if sr.url not in existing_urls:
                        final_results.append(sr)
                        existing_urls.add(sr.url)
            except Exception as e:
                logger.debug(f"Streaming fallback failed: {e}")

        result = {
            "results": [r.model_dump() for r in final_results],
            "sources_used": [s.value for s in sources_used],
            "search_time_ms": search_time,
            "total_count": len(final_results),
        }

        # Populate caches asynchronously (fire-and-forget)
        asyncio.ensure_future(self._populate_cache(query, result, session))

        return result

    async def _try_cache(self, query: str, session) -> Optional[dict]:
        """Try Redis cache first, then DB cache."""
        # 1. Redis (fastest)
        from core.cache import RedisCache
        cached = await RedisCache.get(query)
        if cached:
            cached["from_cache"] = "redis"
            return cached

        # 2. PostgreSQL cache
        if session:
            from core.services import CacheService
            cached = await CacheService.get(session, query)
            if cached:
                # Promote to Redis
                asyncio.ensure_future(RedisCache.set(query, cached))
                cached["from_cache"] = "database"
                return cached

        return None

    async def _enrich_cloud_links(self, results: list) -> None:
        """Background task: extract 提取码 for cloud drive links."""
        try:
            from core.cloud_extractor import CloudExtractionPipeline

            for r in results:
                url = r.url if hasattr(r, "url") else r.get("url", "")
                rtype = r.resource_type if hasattr(r, "resource_type") else r.get("resource_type", "")
                if rtype in ("cloud_drive",) and "baidu" in url.lower():
                    code = await CloudExtractionPipeline.process(url)
                    if code and hasattr(r, "extra"):
                        r.extra["extraction_code"] = code.code
        except Exception as e:
            logger.debug(f"Cloud link enrichment failed: {e}")

    async def _populate_cache(self, query: str, result: dict, session) -> None:
        """Save search results to both cache layers."""
        # Save to Redis
        from core.cache import RedisCache
        await RedisCache.set(query, result)

        # Save to PostgreSQL
        if session:
            try:
                from core.services import CacheService
                await CacheService.set(
                    session,
                    query,
                    result["results"],
                    result["total_count"],
                    result["search_time_ms"],
                    result["sources_used"],
                )
            except Exception as e:
                logger.debug(f"Failed to cache in DB: {e}")
