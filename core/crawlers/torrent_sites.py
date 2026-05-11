"""Concrete crawler implementations for specific torrent/magnet sites."""

import logging

from core.crawlers.base import BaseCrawler, StaticCrawler

logger = logging.getLogger(__name__)


class PirateBayCrawler(StaticCrawler):
    """Crawler for The Pirate Bay."""

    pass  # Uses the generic StaticCrawler with config from config.yaml


class _1337xCrawler(StaticCrawler):
    """Crawler for 1337x."""

    async def search(self, query: str, max_results: int = 20) -> list:
        """1337x requires an extra level of indirection - click into torrent page for magnet."""
        search_url = self._build_search_url(query)
        html = await self.fetch_page(search_url)
        if not html:
            return []

        soup = self.make_soup(html)
        selectors = self.config.get("selectors", {})
        results = []

        rows = soup.select(selectors.get("result_container", ""))
        if not rows:
            return results

        for row in rows[:max_results]:
            try:
                # Get title and torrent detail page link
                title_el = row.select_one(selectors.get("title", ""))
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                detail_link = title_el.get("href", "")
                detail_url = f"{self.base_url.rstrip('/')}{detail_link}"

                # Get seeders/leechers
                seeders = None
                if selectors.get("seeders"):
                    se_el = row.select_one(selectors["seeders"])
                    if se_el:
                        try:
                            seeders = int(se_el.get_text(strip=True))
                        except (ValueError, TypeError):
                            seeders = None

                # Fetch the detail page to get the magnet link
                magnet_url = await self._fetch_magnet_from_detail(detail_url)

                if not magnet_url:
                    continue

                from core.models.schemas import ResourceType, SearchResult, SearchSource
                from core.link_extractor import extract_resolution_from_title, parse_size_string

                # Get size
                size = None
                if selectors.get("size"):
                    size_el = row.select_one(selectors["size"])
                    if size_el:
                        size = size_el.get_text(strip=True)

                resolution = extract_resolution_from_title(title)

                result = SearchResult(
                    title=title,
                    resource_type=ResourceType.MAGNET,
                    url=magnet_url,
                    source=SearchSource.WEBSITE_1337X,
                    size=size,
                    seeders=seeders,
                    resolution=resolution,
                )
                result.calculate_quality_score()
                results.append(result)

            except Exception as e:
                logger.debug(f"Error parsing 1337x result: {e}")
                continue

        return results

    async def _fetch_magnet_from_detail(self, detail_url: str) -> str | None:
        """Visit a torrent detail page to extract the magnet link."""
        html = await self.fetch_page(detail_url)
        if not html:
            return None
        soup = self.make_soup(html)
        magnet_el = soup.select_one("a[href^='magnet:']")
        if magnet_el:
            return magnet_el.get("href", "")
        return None


class YTSCrawler(StaticCrawler):
    """Crawler for YTS (YIFY) torrents."""

    async def search(self, query: str, max_results: int = 20) -> list:
        """YTS requires clicking through to the movie page to access torrent links."""
        search_url = self._build_search_url(query)
        html = await self.fetch_page(search_url)
        if not html:
            return []

        soup = self.make_soup(html)
        selectors = self.config.get("selectors", {})
        results = []

        movie_wraps = soup.select(selectors.get("result_container", ""))
        if not movie_wraps:
            return results

        for wrap in movie_wraps[:max_results]:
            try:
                title_el = wrap.select_one(selectors.get("title", ""))
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                movie_link = title_el.get("href", "")
                movie_url = normalize_url(movie_link, self.base_url)

                # Get year
                year = None
                if selectors.get("year"):
                    year_el = wrap.select_one(selectors["year"])
                    if year_el:
                        try:
                            year = int(year_el.get_text(strip=True))
                        except (ValueError, TypeError):
                            pass

                # Fetch movie page for torrent links
                torrents = await self._fetch_torrents_from_movie_page(movie_url)

                for torrent in torrents:
                    from core.models.schemas import ResourceType, SearchResult, SearchSource

                    result = SearchResult(
                        title=f"{title} {torrent.get('quality', '')}",
                        resource_type=ResourceType.TORRENT,
                        url=torrent["url"],
                        source=SearchSource.YTS,
                        size=torrent.get("size"),
                        seeders=torrent.get("seeders"),
                        resolution=torrent.get("quality"),
                    )
                    result.calculate_quality_score()
                    results.append(result)

            except Exception as e:
                logger.debug(f"Error parsing YTS result: {e}")
                continue

        return results

    async def _fetch_torrents_from_movie_page(self, movie_url: str) -> list[dict]:
        """Extract torrent download links from a YTS movie page."""
        html = await self.fetch_page(movie_url)
        if not html:
            return []
        soup = self.make_soup(html)
        torrents = []
        for row in soup.select("div.download-info a"):
            href = row.get("href", "")
            if href and "/torrent/download/" in href:
                quality = row.get_text(strip=True)
                torrent_url = normalize_url(href, self.base_url)
                torrents.append({
                    "url": torrent_url,
                    "quality": quality,
                    "size": None,
                    "seeders": None,
                })
        return torrents


def normalize_url(url: str, base_url: str) -> str:
    """Convert relative URLs to absolute URLs."""
    if url.startswith("http://") or url.startswith("https://") or url.startswith("magnet:") or url.startswith("ed2k://"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{base_url.rstrip('/')}{url}"
    return f"{base_url.rstrip('/')}/{url}"
