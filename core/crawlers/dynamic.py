"""Dynamic crawler using Playwright for JavaScript-rendered pages.

Handles sites that require:
- JavaScript rendering (SPA, dynamic content)
- Cloudflare challenge bypass
- Cookie consent / popup dismissal
- Simulated human behavior (scrolling, clicks)
"""

import asyncio
import logging
import random
import re
from typing import Optional

from core.crawlers.base import USER_AGENTS
from core.link_extractor import (
    extract_info_hash,
    extract_links_from_html,
    extract_resolution_from_title,
    normalize_url,
    parse_size_string,
)
from core.models.schemas import ResourceType, SearchResult, SearchSource

logger = logging.getLogger(__name__)

# Stealth viewport configurations
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
]


class DynamicCrawlerConfig:
    """Configuration for a dynamic crawler instance."""

    def __init__(
        self,
        name: str,
        search_url_template: str,
        source: SearchSource,
        wait_selector: Optional[str] = None,
        result_selector: Optional[str] = None,
        title_selector: Optional[str] = None,
        link_selector: Optional[str] = None,
        seeders_selector: Optional[str] = None,
        size_selector: Optional[str] = None,
        scroll_to_bottom: bool = False,
        dismiss_cookie: Optional[str] = None,
        wait_timeout: int = 20000,
    ):
        self.name = name
        self.search_url_template = search_url_template
        self.source = source
        self.wait_selector = wait_selector
        self.result_selector = result_selector
        self.title_selector = title_selector
        self.link_selector = link_selector
        self.seeders_selector = seeders_selector
        self.size_selector = size_selector
        self.scroll_to_bottom = scroll_to_bottom
        self.dismiss_cookie = dismiss_cookie
        self.wait_timeout = wait_timeout


# Pre-defined crawler configurations for popular sites
CRAWLER_CONFIGS: dict[str, DynamicCrawlerConfig] = {
    "torrentgalaxy": DynamicCrawlerConfig(
        name="TorrentGalaxy",
        search_url_template="https://torrentgalaxy.to/torrents.php?search={query}#results",
        source=SearchSource.OTHER,
        wait_selector="div.tgxtable",
        result_selector="div.tgxtable div.tgxtable-row",
        title_selector="a.txlight",
        link_selector="a[href^='magnet:']",
        seeders_selector="span[title^='Seeders']",
        size_selector="span[title^='Size']",
        scroll_to_bottom=True,
        dismiss_cookie="button#cookies_accept",
    ),
    "limetorrents": DynamicCrawlerConfig(
        name="LimeTorrents",
        search_url_template="https://www.limetorrents.info/search/all/{query}/",
        source=SearchSource.OTHER,
        wait_selector="table.table2",
        result_selector="table.table2 tr",
        title_selector="a:not(.csprite_dl14)",
        link_selector="a[href^='magnet:']",
        seeders_selector="td.seed",
        wait_timeout=15000,
    ),
    "nyaasi": DynamicCrawlerConfig(
        name="Nyaa.si",
        search_url_template="https://nyaa.si/?f=0&c=0_0&q={query}",
        source=SearchSource.OTHER,
        wait_selector="table.torrent-list",
        result_selector="table.torrent-list tr",
        title_selector="a:not(.comments)",
        link_selector="a[href^='magnet:']",
        seeders_selector="td:nth-child(6)",
        size_selector="td:nth-child(4)",
    ),
}


class PlaywrightCrawler:
    """Async crawler using Playwright for dynamic page rendering.

    Usage:
        crawler = PlaywrightCrawler()
        results = await crawler.search("site_name", "movie name")
        await crawler.close()

    Note: Requires 'playwright install chromium' to be run once.
    """

    _browser = None
    _lock = asyncio.Lock()
    _initialized = False

    def __init__(self):
        self.page = None
        self.context = None

    @classmethod
    async def ensure_browser(cls):
        """Lazy initialize the Playwright browser (shared singleton)."""
        if cls._browser is not None:
            return cls._browser

        async with cls._lock:
            if cls._browser is not None:
                return cls._browser

            try:
                from playwright.async_api import async_playwright

                p = await async_playwright().start()
                cls._browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
                cls._initialized = True
                logger.info("Playwright Chromium browser launched")
            except Exception as e:
                logger.error(f"Failed to launch Playwright browser: {e}")
                logger.error("Run: playwright install chromium")
                cls._browser = None

            return cls._browser

    async def _create_page(self):
        """Create a new stealth page in a new context."""
        browser = await self.ensure_browser()
        if not browser:
            return None

        # Create isolated context with stealth settings
        self.context = await browser.new_context(
            viewport=random.choice(VIEWPORTS),
            user_agent=random.choice(USER_AGENTS),
            locale="en-US",
            timezone_id="America/New_York",
            permissions=[],
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        # Set extra HTTP headers
        await self.context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        self.page = await self.context.new_page()
        return self.page

    async def search(
        self, site_key: str, query: str, max_results: int = 20
    ) -> list[SearchResult]:
        """Search a dynamic site using Playwright.

        Args:
            site_key: Key from CRAWLER_CONFIGS (e.g. 'torrentgalaxy').
            query: Search query (movie name).
            max_results: Max results to return.

        Returns:
            List of SearchResult objects.
        """
        config = CRAWLER_CONFIGS.get(site_key)
        if not config:
            logger.warning(f"Unknown crawler config: {site_key}")
            return []

        page = await self._create_page()
        if not page:
            logger.warning(f"[{config.name}] Browser unavailable")
            return []

        search_url = config.search_url_template.replace("{query}", query.replace(" ", "+"))
        results = []

        try:
            logger.info(f"[{config.name}] Navigating to {search_url[:80]}...")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # Wait for content to load
            if config.wait_selector:
                try:
                    await page.wait_for_selector(
                        config.wait_selector, timeout=config.wait_timeout
                    )
                except Exception:
                    logger.debug(f"[{config.name}] Wait selector not found, continuing")

            # Dismiss cookie consent if configured
            if config.dismiss_cookie:
                try:
                    btn = await page.query_selector(config.dismiss_cookie)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

            # Scroll to bottom to trigger lazy loading
            if config.scroll_to_bottom:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

            # Get page content
            html = await page.content()

            # Parse results
            results = self._parse_results(html, config, max_results)

        except Exception as e:
            logger.warning(f"[{config.name}] Crawl failed: {e}")

        finally:
            await self._cleanup()

        return results

    def _parse_results(
        self, html: str, config: DynamicCrawlerConfig, max_results: int
    ) -> list[SearchResult]:
        """Parse search results from HTML using configured selectors."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        results = []

        containers = (
            soup.select(config.result_selector) if config.result_selector else [soup]
        )

        for container in containers[:max_results]:
            try:
                # Extract title
                title = None
                if config.title_selector:
                    el = container.select_one(config.title_selector)
                    if el:
                        title = el.get_text(strip=True)

                if not title or len(title) < 3:
                    continue

                # Extract link
                link = None
                if config.link_selector:
                    el = container.select_one(config.link_selector)
                    if el:
                        link = el.get("href", "")

                if not link:
                    continue

                # Determine resource type
                resource_type = ResourceType.MAGNET if link.startswith("magnet:") else ResourceType.TORRENT

                # Extract seeders
                seeders = None
                if config.seeders_selector:
                    el = container.select_one(config.seeders_selector)
                    if el:
                        try:
                            seeders = int(re.sub(r"\D", "", el.get_text(strip=True)))
                        except (ValueError, TypeError):
                            seeders = None

                # Extract size
                size = None
                if config.size_selector:
                    el = container.select_one(config.size_selector)
                    if el:
                        size = el.get_text(strip=True)

                resolution = extract_resolution_from_title(title)
                info_hash = extract_info_hash(link) if link.startswith("magnet:") else None

                result = SearchResult(
                    title=title,
                    resource_type=resource_type,
                    url=link,
                    info_hash=info_hash,
                    source=config.source,
                    size=size,
                    seeders=seeders,
                    resolution=resolution,
                )
                result.calculate_quality_score()
                results.append(result)

            except Exception as e:
                logger.debug(f"Parse error: {e}")
                continue

        return results

    async def _cleanup(self):
        """Close page and context after each search."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
        except Exception:
            pass
        finally:
            self.page = None
            self.context = None

    @classmethod
    async def close(cls):
        """Close the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                try:
                    await cls._browser.close()
                    cls._browser = None
                    cls._initialized = False
                    logger.info("Playwright browser closed")
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")


class DynamicCrawlerManager:
    """Manages multiple dynamic crawlers and aggregates results."""

    def __init__(self):
        self.enabled_sites = list(CRAWLER_CONFIGS.keys())

    async def search_all(
        self, query: str, max_results: int = 30
    ) -> list[SearchResult]:
        """Run all enabled dynamic crawlers concurrently."""
        crawler = PlaywrightCrawler()
        tasks = [
            crawler.search(site, query, max_results)
            for site in self.enabled_sites
        ]

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate
        seen = set()
        merged: list[SearchResult] = []

        for results in all_results:
            if isinstance(results, Exception):
                logger.warning(f"Dynamic crawler failed: {results}")
                continue
            for r in results:
                key = r.info_hash or r.url
                if key and key not in seen:
                    seen.add(key)
                    merged.append(r)

        merged.sort(key=lambda r: r.quality_score, reverse=True)
        await PlaywrightCrawler.close()
        return merged[:max_results]
