"""Shared test fixtures and configuration for CineSeeker tests."""

import asyncio
import os
import sys
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =============================================================================
# Test data: sample magnet links for unit tests
# =============================================================================

SAMPLE_MAGNET = (
    "magnet:?xt=urn:btih:"
    "08ada5a7a6183aae1e09d831df6748d566095a10"
    "&dn=Sample+Movie+1080p&tr=udp://tracker.opentrackr.org:1337"
)
SAMPLE_MAGNET_2 = (
    "magnet:?xt=urn:btih:"
    "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
    "&dn=Another+Movie+2160p"
)
SAMPLE_INFO_HASH = "08ada5a7a6183aae1e09d831df6748d566095a10"
SAMPLE_TORRENT_URL = "https://example.com/files/movie.torrent"
SAMPLE_ED2K_LINK = "ed2k://|file|Sample.Movie.1080p.mkv|1234567890|abcdef1234567890abcdef1234567890|/"
SAMPLE_CLOUD_BAIDU = "https://pan.baidu.com/s/1abc123def456"
SAMPLE_CLOUD_ALIYUN = "https://www.aliyundrive.com/s/abc123def"
SAMPLE_CLOUD_QUARK = "https://pan.quark.cn/s/abc123def456"
SAMPLE_STREAM_URL = "https://example.com/stream/video.m3u8?token=abc"

# Sample HTML with embedded magnet/ED2K links
SAMPLE_HTML = f"""<html>
<body>
  <a href="{SAMPLE_MAGNET}">Magnet Link</a>
  <a href="{SAMPLE_TORRENT_URL}">Torrent File</a>
  <a href="{SAMPLE_ED2K_LINK}">ED2K Link</a>
  <a href="{SAMPLE_CLOUD_BAIDU}">Baidu Cloud</a>
  <div>Some other content</div>
</body>
</html>"""


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio backend for anyio-based tests."""
    return "asyncio"
