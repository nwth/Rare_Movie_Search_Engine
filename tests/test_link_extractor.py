"""Unit tests for the link extraction utilities."""

import pytest
from bs4 import BeautifulSoup

from core.link_extractor import (
    CLOUD_DRIVE_PATTERNS,
    detect_resource_type,
    extract_from_soup,
    extract_info_hash,
    extract_links_from_html,
    extract_resolution_from_title,
    normalize_url,
    parse_size_string,
)
from core.models.schemas import ResourceType


# =============================================================================
# Tests: extract_info_hash
# =============================================================================

class TestExtractInfoHash:
    def test_valid_magnet(self):
        """Extract hash from a valid magnet link."""
        magnet = (
            "magnet:?xt=urn:btih:"
            "08ada5a7a6183aae1e09d831df6748d566095a10"
            "&dn=Test&tr=udp://tracker.org"
        )
        assert extract_info_hash(magnet) == "08ada5a7a6183aae1e09d831df6748d566095a10"

    def test_returns_lowercase(self):
        """Hash should always be returned in lowercase."""
        magnet = "magnet:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01"
        assert extract_info_hash(magnet) == "abcdef0123456789abcdef0123456789abcdef01"

    def test_invalid_url(self):
        """Return None for non-magnet URLs."""
        assert extract_info_hash("https://example.com") is None
        assert extract_info_hash("") is None
        assert extract_info_hash("not a link") is None

    def test_magnet_without_hash(self):
        """Return None if magnet has no info hash."""
        assert extract_info_hash("magnet:?dn=Test&tr=udp://tracker.org") is None

    def test_short_hash(self):
        """Return None if hash is not exactly 40 chars."""
        assert extract_info_hash("magnet:?xt=urn:btih:abc123") is None


# =============================================================================
# Tests: detect_resource_type
# =============================================================================

class TestDetectResourceType:
    def test_magnet(self):
        assert detect_resource_type("magnet:?xt=urn:btih:abc") == ResourceType.MAGNET

    def test_torrent_url(self):
        assert detect_resource_type("https://example.com/file.torrent") == ResourceType.TORRENT
        assert detect_resource_type("http://example.com/a.torrent?param=1") == ResourceType.TORRENT

    def test_ed2k(self):
        assert detect_resource_type("ed2k://|file|movie.mkv|123|/") == ResourceType.ED2K

    def test_baidu_pan(self):
        assert detect_resource_type("https://pan.baidu.com/s/1abc123") == ResourceType.CLOUD_DRIVE

    def test_aliyundrive(self):
        assert detect_resource_type("https://www.aliyundrive.com/s/abc123") == ResourceType.CLOUD_DRIVE

    def test_quark(self):
        assert detect_resource_type("https://pan.quark.cn/s/abc123") == ResourceType.CLOUD_DRIVE

    def test_123pan(self):
        assert detect_resource_type("https://www.123pan.com/s/abc123") == ResourceType.CLOUD_DRIVE

    def test_115(self):
        assert detect_resource_type("https://115.com/s/abc123") == ResourceType.CLOUD_DRIVE

    def test_stream_m3u8(self):
        assert detect_resource_type("https://example.com/stream.m3u8") == ResourceType.STREAM

    def test_stream_mp4(self):
        assert detect_resource_type("https://example.com/video.mp4?token=abc") == ResourceType.STREAM

    def test_webm(self):
        assert detect_resource_type("https://example.com/video.webm") == ResourceType.STREAM

    def test_unknown_falls_to_stream(self):
        """Unknown URL types should fall back to STREAM."""
        assert detect_resource_type("https://example.com/page.html") == ResourceType.STREAM


# =============================================================================
# Tests: extract_links_from_html
# =============================================================================

class TestExtractLinksFromHtml:
    def test_extract_magnet(self):
        html = '<a href="magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10">link</a>'
        links = extract_links_from_html(html)
        assert len(links) == 1
        assert links[0]["type"] == ResourceType.MAGNET
        assert links[0]["info_hash"] == "08ada5a7a6183aae1e09d831df6748d566095a10"

    def test_extract_multiple_link_types(self):
        """Extract magnet, torrent, ED2K, and cloud drive links from HTML."""
        html = """
        <a href="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">Magnet</a>
        <a href="https://example.com/file.torrent">Torrent</a>
        <a href="ed2k://|file|movie.mkv|123|/">ED2K</a>
        <a href="https://pan.baidu.com/s/1abc123">Baidu</a>
        """
        links = extract_links_from_html(html)
        types = {link["type"] for link in links}
        assert ResourceType.MAGNET in types
        assert ResourceType.TORRENT in types
        assert ResourceType.ED2K in types
        assert ResourceType.CLOUD_DRIVE in types

    def test_deduplication(self):
        """Duplicate URLs should not appear twice."""
        html = f"""
        <a href="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">A</a>
        <a href="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">A again</a>
        """
        links = extract_links_from_html(html)
        assert len(links) == 1

    def test_empty_html(self):
        assert extract_links_from_html("") == []
        assert extract_links_from_html("<html><body>No links here</body></html>") == []

    def test_cloud_drive_variants(self):
        """Test all cloud drive patterns are matched."""
        html = """
        <a href="https://pan.baidu.com/s/1abc123def456">Baidu</a>
        <a href="https://www.aliyundrive.com/s/abc123def">Aliyun</a>
        <a href="https://pan.quark.cn/s/abc123def456">Quark</a>
        <a href="https://www.123pan.com/s/abc123">123Pan</a>
        <a href="https://115.com/s/abc123">115</a>
        """
        links = extract_links_from_html(html)
        assert len(links) == 5
        assert all(l["type"] == ResourceType.CLOUD_DRIVE for l in links)


# =============================================================================
# Tests: extract_resolution_from_title
# =============================================================================

class TestExtractResolution:
    def test_2160p(self):
        assert extract_resolution_from_title("Movie 2160p UHD") == "2160P"

    def test_4k(self):
        assert extract_resolution_from_title("Movie 4K HDR") == "4K"

    def test_1080p(self):
        assert extract_resolution_from_title("Movie 1080p BluRay") == "1080P"

    def test_720p(self):
        assert extract_resolution_from_title("Movie 720p HD") == "720P"

    def test_480p(self):
        assert extract_resolution_from_title("Movie 480p") == "480P"

    def test_no_resolution(self):
        assert extract_resolution_from_title("Just a Movie Name") is None

    def test_case_insensitive(self):
        assert extract_resolution_from_title("Movie 1080P") == "1080P"
        assert extract_resolution_from_title("Movie 4k") == "4K"

    def test_resolution_in_context(self):
        assert extract_resolution_from_title("Movie.Name.2024.1080p.WEB-DL.DDP5.1") == "1080P"
        assert extract_resolution_from_title("Movie.2024.2160p.AMZN.WEBRip") == "2160P"


# =============================================================================
# Tests: parse_size_string
# =============================================================================

class TestParseSize:
    def test_gigabytes(self):
        result = parse_size_string("2.5 GB")
        assert result is not None
        assert result == 2.5 * 1024 ** 3

    def test_megabytes(self):
        result = parse_size_string("700 MB")
        assert result is not None
        assert result == 700 * 1024 ** 2

    def test_kilobytes(self):
        result = parse_size_string("500 KB")
        assert result is not None
        assert result == 500 * 1024

    def test_terabytes(self):
        result = parse_size_string("1.2 TB")
        assert result is not None
        assert result == 1.2 * 1024 ** 4

    def test_bytes(self):
        result = parse_size_string("512 B")
        assert result is not None
        assert result == 512

    def test_no_units(self):
        assert parse_size_string("unknown") is None

    def test_empty_string(self):
        assert parse_size_string(None) is None
        assert parse_size_string("") is None

    def test_case_insensitive(self):
        gb = parse_size_string("1 GB")
        assert gb == parse_size_string("1 gb")
        assert gb == parse_size_string("1 Gb")


# =============================================================================
# Tests: normalize_url
# =============================================================================

class TestNormalizeUrl:
    def test_absolute_https(self):
        assert normalize_url("https://example.com/page", "https://base.com") == "https://example.com/page"

    def test_absolute_http(self):
        assert normalize_url("http://example.com/page", "https://base.com") == "http://example.com/page"

    def test_magnet(self):
        url = "magnet:?xt=urn:btih:abc"
        assert normalize_url(url, "https://base.com") == url

    def test_ed2k(self):
        url = "ed2k://|file|movie.mkv|123|/"
        assert normalize_url(url, "https://base.com") == url

    def test_protocol_relative(self):
        assert normalize_url("//example.com/page", "https://base.com") == "https://example.com/page"

    def test_root_relative(self):
        assert normalize_url("/path/to/page", "https://base.com") == "https://base.com/path/to/page"

    def test_relative_path(self):
        assert normalize_url("relative/path", "https://base.com/dir/") == "https://base.com/dir/relative/path"

    def test_base_without_trailing_slash(self):
        assert normalize_url("page", "https://base.com") == "https://base.com/page"


# =============================================================================
# Tests: extract_from_soup
# =============================================================================

class TestExtractFromSoup:
    def test_extract_by_selector(self):
        html = '<a href="https://example.com/1">One</a><a href="https://example.com/2">Two</a>'
        soup = BeautifulSoup(html, "lxml")
        links = extract_from_soup(soup, "a")
        assert len(links) == 2
        assert "https://example.com/1" in links

    def test_empty_soup(self):
        soup = BeautifulSoup("<html></html>", "lxml")
        assert extract_from_soup(soup, "a") == []

    def test_no_matching_selector(self):
        html = '<div class="movie">Content</div>'
        soup = BeautifulSoup(html, "lxml")
        assert extract_from_soup(soup, "a") == []
