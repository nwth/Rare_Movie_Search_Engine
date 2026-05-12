"""Cloud drive crawlers for Baidu, AliYun, Quark, and 123Pan.

These crawlers search public cloud drive shares for movie resources.
They work by using Google Dorking to find share links, then
extracting the resource info from the share page.
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from core.crawlers.base import BaseCrawler, StaticCrawler
from core.link_extractor import normalize_url
from core.models.schemas import ResourceType, SearchResult, SearchSource

logger = logging.getLogger(__name__)


class BaiduPanCrawler(BaseCrawler):
    """Search Baidu Pan (pan.baidu.com) for shared movie files.

    Note: Baidu Pan requires extraction codes (提取码) for most shares.
    This crawler collects share links; codes are handled separately.
    """

    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Search Baidu Pan share links via Google Dork results.

        The actual search is done via Google Dorking (site:pan.baidu.com).
        This crawler can later be extended to parse Baidu's internal search.
        """
        # Baidu Pan shares are primarily found via Google Dorking
        # (configured in config.yaml as dork queries)
        # This crawler is a placeholder for future direct Baidu API integration
        return []


class AliYunDriveCrawler(BaseCrawler):
    """Search Aliyun Drive (aliyundrive.com) for shared movie files."""

    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Search Aliyun Drive via Google Dorking results.

        Aliyun share links are found via:
        site:aliyundrive.com/s/ {query}
        """
        return []


class QuarkPanCrawler(BaseCrawler):
    """Search Quark Pan (pan.quark.cn) for shared movie files."""

    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Search Quark Pan shares.

        Quark shares are found via:
        site:pan.quark.cn {query}
        """
        return []


class PanDorkCrawler(StaticCrawler):
    """Enhanced cloud drive crawler that parses Google Dork result pages.

    This crawler directly queries Google with cloud-drive-specific dorks
    and parses the results to extract share links with metadata.
    """

    def __init__(self, name: str, dork_query: str, drive_type: ResourceType,
                 weight: float = 0.8, proxy: Optional[str] = None):
        config = {
            "name": name,
            "base_url": "https://www.google.com",
            "search_path": "/search?q=",
            "selectors": {},
        }
        super().__init__(config, proxy)
        self.dork_query = dork_query
        self.drive_type = drive_type
        self.weight = weight

    async def search(self, query: str, max_results: int = 20) -> list[SearchResult]:
        """Execute a cloud-drive-specific Google Dork search."""
        import httpx
        from core.crawlers.base import USER_AGENTS
        import random

        # Build the dork query
        full_query = self.dork_query.replace("{query}", query)
        search_url = (
            f"https://www.google.com/search?q={full_query.replace(' ', '+')}"
            f"&num={min(max_results * 2, 30)}"
        )

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        results = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            try:
                resp = await client.get(search_url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                logger.debug(f"PanDork crawler failed: {e}")
                return results

        # Extract cloud drive links from search results
        from core.link_extractor import extract_links_from_html
        links = extract_links_from_html(resp.text)

        seen = set()
        for link_data in links:
            if link_data["type"] != ResourceType.CLOUD_DRIVE:
                continue

            url = link_data["url"]
            if url in seen:
                continue
            seen.add(url)

            # Find the title from the search result snippet
            title = self._find_snippet_title(soup, url) or url

            result = SearchResult(
                title=title,
                resource_type=ResourceType.CLOUD_DRIVE,
                url=url,
                source=SearchSource.GOOGLE_DORK,
            )
            result.quality_score = self.weight * 2.5
            results.append(result)

        return results[:max_results]

    def _find_snippet_title(self, soup: BeautifulSoup, target_url: str) -> Optional[str]:
        """Extract title from search result containing the URL."""
        for result_div in soup.select("div.g, div.Gx5Zad"):
            link = result_div.select_one("a[href]")
            if link and target_url in link.get("href", ""):
                title_el = result_div.select_one("h3")
                if title_el:
                    return title_el.get_text(strip=True)
        return None
