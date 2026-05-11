"""Link validity checker for CineSeeker.

Asynchronously checks if download links are still valid.
"""

import asyncio
import logging
from typing import Optional

import httpx

from core.crawlers.base import USER_AGENTS

logger = logging.getLogger(__name__)


class LinkValidator:
    """Validates whether resource download links are still alive."""

    @staticmethod
    async def check_magnet(info_hash: str) -> bool:
        """Check if a magnet link has active peers via DHT lookup.

        For Phase 2, we use a simple heuristic:
        try to fetch from a public DHT indexer.
        """
        if not info_hash:
            return True  # assume valid if no hash to check

        # Try querying a public DHT tracker
        test_urls = [
            f"https://torrentlookup.com/torrent/{info_hash}",
            f"https://btcache.me/torrent/{info_hash}",
        ]

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            follow_redirects=True,
        ) as client:
            for url in test_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    continue
        return False

    @staticmethod
    async def check_http_url(url: str, timeout: float = 5.0) -> bool:
        """Check if an HTTP/HTTPS URL is accessible."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                resp = await client.head(url)
                return resp.status_code < 400
        except (httpx.TimeoutException, httpx.ConnectError):
            return False
        except Exception as e:
            logger.debug(f"HTTP check failed for {url[:60]}: {e}")
            return False

    @staticmethod
    async def check_cloud_drive(url: str) -> bool:
        """Check if a cloud drive share link is accessible."""
        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(8.0),
                follow_redirects=True,
                headers=headers,
            ) as client:
                resp = await client.get(url)
                # Cloud drives return 200 even for expired links but show error page
                # A 404 or redirect to login usually means expired
                if resp.status_code in (200, 202):
                    return True
                return False
        except Exception:
            return False

    @staticmethod
    async def validate(url: str, resource_type: str = "magnet",
                       info_hash: Optional[str] = None) -> bool:
        """Universal validator - dispatches to correct check based on type."""
        if resource_type in ("magnet",):
            if info_hash:
                return await LinkValidator.check_magnet(info_hash)
            return True  # can't validate without hash

        if resource_type in ("cloud_drive",):
            return await LinkValidator.check_cloud_drive(url)

        if url.startswith(("http://", "https://")):
            return await LinkValidator.check_http_url(url)

        return True  # unknown type, assume valid

    @staticmethod
    async def batch_validate(
        urls: list[tuple[str, str, Optional[str]]],
        concurrency: int = 5
    ) -> list[bool]:
        """Validate multiple links concurrently.

        Args:
            urls: List of (url, resource_type, info_hash) tuples.

        Returns:
            List of boolean validity results in same order.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _check(item: tuple) -> bool:
            async with semaphore:
                url, rtype, ihash = item
                return await LinkValidator.validate(url, rtype, ihash)

        tasks = [_check(item) for item in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if isinstance(r, bool) else False
            for r in results
        ]
