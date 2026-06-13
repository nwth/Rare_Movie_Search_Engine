"""Online streaming URL parser - fallback when no download links found.

Extracts embedded player URLs, streaming links (m3u8, mp4, etc.)
from movie resource sites when magnet/cloud drive resources are unavailable.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from core.crawlers.base import USER_AGENTS
from core.models.schemas import ResourceType, SearchResult, SearchSource

logger = logging.getLogger(__name__)

# Streaming URL patterns
STREAM_PATTERNS = {
    "m3u8": re.compile(r"https?://[^\s'\"<>]+\.m3u8[^\s'\"<>]*"),
    "mp4": re.compile(r"https?://[^\s'\"<>]+\.mp4[^\s'\"<>]*"),
    "webm": re.compile(r"https?://[^\s'\"<>]+\.webm[^\s'\"<>]*"),
    "iframe": re.compile(r'<iframe[^>]+src=["\'](https?://[^"\']+)["\']'),
    "embed": re.compile(r'<embed[^>]+src=["\'](https?://[^"\']+)["\']'),
    "video_src": re.compile(r'<video[^>]+src=["\'](https?://[^"\']+)["\']'),
}

# Known streaming site patterns
STREAMING_DOMAINS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "bilibili.com", "iqiyi.com", "youku.com", "tudou.com",
    "sohu.com", "tencent.com", "letv.com", "mgtv.com",
    "netflix.com", "disneyplus.com", "hulu.com", "primevideo.com",
    "archive.org", "ok.ru", "vk.com", "facebook.com/watch",
]

# Common embedded player URL patterns
EMBED_PATTERNS = [
    re.compile(r"(https?://[^/]+/player/[^\s'\"<>&?]+)"),
    re.compile(r"(https?://[^/]+/embed/[^\s'\"<>&?]+)"),
    re.compile(r"(https?://[^/]+/play/[^\s'\"<>&?]+)"),
    re.compile(r"(https?://[^/]+/v/[^\s'\"<>&?]+)"),
    re.compile(r"(https?://[^/]+/video/[^\s'\"<>&?]+)"),
    re.compile(r"(https?://[^/]+/e/[^\s'\"<>&?]+)"),
]


def is_streaming_domain(url: str) -> bool:
    """Check if a URL belongs to a known streaming platform."""
    domain = urlparse(url).netloc.lower()
    return any(sd in domain for sd in STREAMING_DOMAINS)


class StreamParser:
    """Parse streaming/embedded video URLs from web pages."""

    @staticmethod
    def extract_from_html(html: str, page_url: str) -> list[dict]:
        """Extract all streaming URLs from HTML content.

        Returns:
            List of dicts with 'url', 'type', and 'source' keys.
        """
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen = set()

        # 1. Extract from <iframe> tags
        for iframe in soup.find_all("iframe", src=True):
            src = iframe["src"]
            if src and src not in seen:
                seen.add(src)
                full_url = urljoin(page_url, src)
                results.append({
                    "url": full_url,
                    "type": "iframe",
                    "source": urlparse(full_url).netloc,
                })

        # 2. Extract from <video> tags
        for video in soup.find_all("video"):
            # Direct src attribute
            if video.get("src"):
                url = urljoin(page_url, video["src"])
                if url not in seen:
                    seen.add(url)
                    results.append({"url": url, "type": "video", "source": "direct"})
            # <source> children
            for source in video.find_all("source", src=True):
                url = urljoin(page_url, source["src"])
                if url not in seen:
                    seen.add(url)
                    results.append({
                        "url": url,
                        "type": source.get("type", "video").split("/")[-1] or "video",
                        "source": "direct",
                    })

        # 3. Extract streaming links from raw HTML patterns
        for stype, pattern in STREAM_PATTERNS.items():
            for match in pattern.finditer(html):
                url = match.group(0) if stype in ("iframe", "embed", "video_src") else match.group(0)
                if url not in seen:
                    seen.add(url)
                    results.append({
                        "url": url,
                        "type": stype,
                        "source": urlparse(url).netloc,
                    })

        # 4. Extract embed-specific URLs from page text
        for pattern in EMBED_PATTERNS:
            for match in pattern.finditer(html):
                url = match.group(1)
                if url not in seen:
                    seen.add(url)
                    results.append({
                        "url": url,
                        "type": "embed",
                        "source": urlparse(url).netloc,
                    })

        return results

    @staticmethod
    async def search_streaming(query: str, max_results: int = 10) -> list[SearchResult]:
        """Search for streaming links by querying public movie databases.

        Searches Internet Archive and other open movie sources.
        """
        import random
        results = []

        # Search Internet Archive
        archive_url = (
            f"https://archive.org/search?"
            f"query={query.replace(' ', '+')}+AND+mediatype:movies"
        )

        headers = {"User-Agent": random.choice(USER_AGENTS)}

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0), follow_redirects=True, headers=headers
        ) as client:
            try:
                resp = await client.get(archive_url)
                if resp.status_code == 200:
                    archive_results = StreamParser._parse_archive(resp.text, query)
                    results.extend(archive_results)
            except Exception as e:
                logger.debug(f"Archive.org search failed: {e}")

        # Sort by relevance and limit
        results.sort(key=lambda r: r.quality_score or 0, reverse=True)
        return results[:max_results]

    @staticmethod
    def _parse_archive(html: str, query: str) -> list[SearchResult]:
        """Parse Internet Archive search results for streaming movies."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for item in soup.select("div.item-ttl"):
            try:
                title_el = item.select_one("a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "")
                if not link:
                    continue

                full_url = f"https://archive.org{link}" if link.startswith("/") else link

                # Archive.org items have embedded players
                result = SearchResult(
                    title=title,
                    resource_type=ResourceType.STREAM,
                    url=full_url,
                    source=SearchSource.OTHER,
                )
                result.quality_score = 2.0  # Base score for streaming
                results.append(result)

            except Exception:
                continue

        return results

    @staticmethod
    async def extract_player_url(page_url: str) -> Optional[str]:
        """Visit a page and extract the actual video player URL.

        Handles common redirect patterns used by streaming sites:
        - googlevideo.com
        - redirect wrappers
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0), follow_redirects=True
        ) as client:
            try:
                resp = await client.get(page_url)
                html = resp.text

                # Try to find direct video source
                streams = StreamParser.extract_from_html(html, page_url)
                for s in streams:
                    if s["type"] in ("mp4", "m3u8", "webm"):
                        return s["url"]

                # Fall back to iframe src
                for s in streams:
                    if s["type"] == "iframe" and is_streaming_domain(s["url"]):
                        return s["url"]

                return None
            except Exception as e:
                logger.debug(f"Failed to extract player URL: {e}")
                return None


class StreamingFallback:
    """Fallback search for streaming options when no downloads found."""

    @staticmethod
    async def find_streaming(query: str, max_results: int = 5) -> list[SearchResult]:
        """Search for streaming/online viewing options.

        Tries multiple sources in order:
        1. Internet Archive
        2. Public movie databases
        """
        results = []

        # Source 1: Internet Archive
        archive_results = await StreamParser.search_streaming(query, max_results)
        results.extend(archive_results)

        if results:
            return results[:max_results]

        # Source 2: Known streaming sites via Google dork
        # (This relies on Google Dorking from the main search)
        return results
