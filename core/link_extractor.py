"""Link extraction utilities for parsing Magnet, ED2K, and cloud drive links."""

import hashlib
import re
from typing import Optional

from bs4 import BeautifulSoup

from core.models.schemas import ResourceType

# Regex patterns for various resource links
MAGNET_PATTERN = re.compile(r"magnet:\?xt=urn:btih:([a-fA-F0-9]{40})")
TORRENT_PATTERN = re.compile(r"https?://[^\s'\"]+\.torrent")
ED2K_PATTERN = re.compile(r"ed2k://[^\s'\"]+")
CLOUD_DRIVE_PATTERNS = [
    re.compile(r"https?://pan\.baidu\.com/s/[^\s'\"<>]+"),
    re.compile(r"https?://(www\.)?aliyundrive\.com/s/[^\s'\"<>]+"),
    re.compile(r"https?://(pan\.)?quark\.cn/s/[^\s'\"<>]+"),
    re.compile(r"https?://(www\.)?123pan\.com/s/[^\s'\"<>]+"),
    re.compile(r"https?://(www\.)?115\.com/s/[^\s'\"<>]+"),
]
STREAM_PATTERN = re.compile(r"https?://[^\s'\"<>]+\.(m3u8|mp4|webm)(\?[^\s'\"]*)?")


def extract_info_hash(magnet_url: str) -> Optional[str]:
    """Extract the InfoHash from a magnet link."""
    match = MAGNET_PATTERN.search(magnet_url)
    if match:
        return match.group(1).lower()
    return None


def detect_resource_type(url: str) -> ResourceType:
    """Detect the type of resource from its URL."""
    if url.startswith("magnet:"):
        return ResourceType.MAGNET
    if url.endswith(".torrent") or ".torrent" in url:
        return ResourceType.TORRENT
    if url.startswith("ed2k://"):
        return ResourceType.ED2K
    for pattern in CLOUD_DRIVE_PATTERNS:
        if pattern.search(url):
            return ResourceType.CLOUD_DRIVE
    if STREAM_PATTERN.search(url):
        return ResourceType.STREAM
    return ResourceType.STREAM  # default fallback


def extract_links_from_html(html: str) -> list[dict]:
    """Extract all resource links from raw HTML content.

    Returns:
        List of dicts with 'url', 'type', and 'info_hash' keys.
    """
    links = []
    seen = set()

    # Magnet links
    for match in MAGNET_PATTERN.finditer(html):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            info_hash = extract_info_hash(url)
            links.append({
                "url": url,
                "type": ResourceType.MAGNET,
                "info_hash": info_hash,
            })

    # Torrent files
    for match in TORRENT_PATTERN.finditer(html):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            links.append({
                "url": url,
                "type": ResourceType.TORRENT,
                "info_hash": None,
            })

    # ED2K links
    for match in ED2K_PATTERN.finditer(html):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            links.append({
                "url": url,
                "type": ResourceType.ED2K,
                "info_hash": None,
            })

    # Cloud drive links
    for pattern in CLOUD_DRIVE_PATTERNS:
        for match in pattern.finditer(html):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                links.append({
                    "url": url,
                    "type": ResourceType.CLOUD_DRIVE,
                    "info_hash": None,
                })

    return links


def extract_from_soup(soup: BeautifulSoup, link_selector: str) -> list[str]:
    """Extract links from a BeautifulSoup object using a CSS selector."""
    links = []
    for element in soup.select(link_selector):
        href = element.get("href", "")
        if href:
            links.append(href)
    return links


def normalize_url(url: str, base_url: str) -> str:
    """Convert relative URLs to absolute URLs."""
    if url.startswith("http://") or url.startswith("https://") or url.startswith("magnet:") or url.startswith("ed2k://"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{base_url.rstrip('/')}{url}"
    return f"{base_url.rstrip('/')}/{url}"


def extract_resolution_from_title(title: str) -> Optional[str]:
    """Extract video resolution from title string."""
    patterns = [
        r"\b(2160p|4K|UHD)\b",
        r"\b(1080p|FHD|FullHD)\b",
        r"\b(720p|HD)\b",
        r"\b(480p|SD)\b",
        r"\b(360p)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return None


def parse_size_string(size_str: str) -> Optional[float]:
    """Parse size string like '2.5 GB' or '700 MB' to bytes."""
    if not size_str:
        return None
    match = re.search(r"([\d.]+)\s*(TB|GB|MB|KB|B)", size_str, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return value * multipliers.get(unit, 1)
