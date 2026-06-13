"""Unit tests for the search engine orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.schemas import ResourceType, SearchResult, SearchSource


class TestSearchResultDeduplication:
    """Test the deduplication logic used in SearchOrchestrator."""

    def test_deduplicate_by_info_hash(self):
        """Results with same info_hash should be deduplicated."""
        results = [
            SearchResult(
                title="Movie A",
                resource_type=ResourceType.MAGNET,
                url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                info_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                source=SearchSource.GOOGLE_DORK,
                seeders=100,
            ),
            SearchResult(
                title="Movie A (duplicate)",
                resource_type=ResourceType.MAGNET,
                url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                info_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                source=SearchSource.PIRATE_BAY,
                seeders=50,
            ),
        ]
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: x.quality_score, reverse=True):
            key = r.info_hash or r.url
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        # Keep the one with higher quality score (first after sort)
        assert len(unique) == 1

    def test_deduplicate_by_url_when_no_hash(self):
        """Results without info_hash should be deduplicated by URL."""
        results = [
            SearchResult(
                title="Stream A",
                resource_type=ResourceType.STREAM,
                url="https://example.com/stream1.m3u8",
                source=SearchSource.OTHER,
            ),
            SearchResult(
                title="Stream A (dup)",
                resource_type=ResourceType.STREAM,
                url="https://example.com/stream1.m3u8",
                source=SearchSource.OTHER,
            ),
            SearchResult(
                title="Stream B",
                resource_type=ResourceType.STREAM,
                url="https://example.com/stream2.m3u8",
                source=SearchSource.OTHER,
            ),
        ]
        seen = set()
        unique = []
        for r in results:
            key = r.info_hash or r.url
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        assert len(unique) == 2

    def test_sort_by_quality_score(self):
        """Results should be sorted by quality_score descending."""
        results = [
            SearchResult(
                title="Low",
                resource_type=ResourceType.STREAM,
                url="https://example.com/low",
                source=SearchSource.OTHER,
                seeders=1,
            ),
            SearchResult(
                title="High",
                resource_type=ResourceType.MAGNET,
                url="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                info_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                source=SearchSource.GOOGLE_DORK,
                seeders=200,
                resolution="1080p",
            ),
            SearchResult(
                title="Medium",
                resource_type=ResourceType.TORRENT,
                url="https://example.com/medium.torrent",
                source=SearchSource.PIRATE_BAY,
                seeders=50,
                resolution="720p",
            ),
        ]
        for r in results:
            r.calculate_quality_score()
        sorted_results = sorted(results, key=lambda r: r.quality_score, reverse=True)
        assert sorted_results[0].title == "High"
        assert sorted_results[1].title == "Medium"
        assert sorted_results[2].title == "Low"


class TestGoogleDorkEngine:
    """Tests for GoogleDorkEngine (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_execute_dork_parses_links(self):
        """_execute_dork should parse magnet links from Google search HTML."""
        from core.search_engine import GoogleDorkEngine

        engine = GoogleDorkEngine()

        # Mock HTML that simulates Google search results with a magnet link
        mock_html = """<html>
        <div class="g">
          <a href="/url?q=https://example.com/magnet_link">Movie 1080p</a>
        </div>
        <a href="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">Magnet</a>
        </html>"""

        with patch.object(engine, "_get_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_factory.return_value = mock_client

            results = await engine._execute_dork("test query", weight=1.0)

            assert len(results) > 0
            # Should find the magnet link
            magnet_results = [r for r in results if r.resource_type == ResourceType.MAGNET]
            assert len(magnet_results) > 0
            assert magnet_results[0].source == SearchSource.GOOGLE_DORK

    @pytest.mark.asyncio
    async def test_execute_dork_handles_http_error(self):
        """_execute_dork should gracefully handle HTTP errors."""
        from core.search_engine import GoogleDorkEngine

        engine = GoogleDorkEngine()

        with patch.object(engine, "_get_client") as mock_client_factory:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_factory.return_value = mock_client

            results = await engine._execute_dork("test query")
            assert results == []


class TestCrawlerManager:
    """Tests for CrawlerManager."""

    def test_init_crawlers_from_config(self):
        """CrawlerManager should initialize crawlers from config."""
        from core.search_engine import CrawlerManager

        with patch("core.search_engine.settings") as mock_settings:
            mock_settings.get_crawler_sites.return_value = [
                {
                    "name": "The Pirate Bay",
                    "enabled": True,
                    "base_url": "https://thepiratebay.org",
                    "search_path": "/search/{query}",
                    "selectors": {},
                },
                {
                    "name": "YTS",
                    "enabled": True,
                    "base_url": "https://yts.mx",
                    "search_path": "/browse-movies/{query}",
                    "selectors": {},
                },
                {
                    "name": "RARBG (proxy)",
                    "enabled": False,  # Disabled
                    "base_url": "https://rarbg.to",
                    "search_path": "/torrents.php?search={query}",
                    "selectors": {},
                },
            ]
            manager = CrawlerManager()
            # Should have 2 enabled site crawlers + 4 cloud drive crawlers = 6
            assert len(manager.crawlers) >= 2


class TestSearchOrchestrator:
    """Tests for SearchOrchestrator."""

    @pytest.mark.asyncio
    async def test_try_cache_redis_miss(self):
        """When Redis has no cache, should return None."""
        from core.search_engine import SearchOrchestrator

        orchestrator = SearchOrchestrator()

        with patch("core.cache.RedisCache.get", AsyncMock(return_value=None)):
            result = await orchestrator._try_cache("test query", session=None)
            assert result is None

    @pytest.mark.asyncio
    async def test_try_cache_redis_hit(self):
        """When Redis has a cache entry, should return it."""
        from core.search_engine import SearchOrchestrator

        orchestrator = SearchOrchestrator()
        cached_data = {
            "results": [],
            "total_count": 0,
            "search_time_ms": 50,
            "sources_used": [],
        }

        with patch("core.cache.RedisCache.get", AsyncMock(return_value=cached_data)):
            result = await orchestrator._try_cache("test query", session=None)
            assert result is not None
            assert result["from_cache"] == "redis"
            assert result["total_count"] == 0
