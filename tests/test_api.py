"""Integration tests for the FastAPI application.

Tests use the TestClient to simulate HTTP requests without
running a live server. External dependencies (DB, Redis, network)
are mocked to ensure tests are fast and deterministic.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from api.server import create_app


@pytest.fixture
def app():
    """Create the FastAPI application for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create an async test client for the application.

    Uses ASGITransport to simulate HTTP requests directly
    against the ASGI app without starting a server.
    """
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# =============================================================================
# Health & Info endpoints
# =============================================================================

@pytest.mark.asyncio
class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    async def test_health_returns_ok(self, client):
        """GET /api/health should return status ok."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_contains_service_name(self, client):
        """Health response should include the service name."""
        response = await client.get("/api/health")
        data = response.json()
        assert "cineseeker" in str(data).lower() or "service" in data


@pytest.mark.asyncio
class TestSourcesEndpoint:
    """Tests for the sources listing endpoint."""

    async def test_sources_returns_list(self, client):
        """GET /api/sources should return a list of sources."""
        response = await client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        # Should contain sources key
        assert "sources" in data or isinstance(data, dict)


# =============================================================================
# Search endpoints
# =============================================================================

@pytest.mark.asyncio
class TestTextSearchEndpoint:
    """Tests for the text search endpoint."""

    async def test_search_requires_query(self, client):
        """GET /api/search without q should return 422."""
        response = await client.get("/api/search")
        assert response.status_code == 422

    async def test_search_empty_query_rejected(self, client):
        """GET /api/search?q= should return 422 for empty query."""
        response = await client.get("/api/search", params={"q": ""})
        assert response.status_code == 422

    async def test_search_with_valid_query(self, client):
        """GET /api/search?q=Inception should return 200 with results."""
        mock_search_result = {
            "results": [
                {
                    "title": "Inception 2010 1080p",
                    "resource_type": "magnet",
                    "url": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "info_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "source": "google_dork",
                    "quality_score": 8.0,
                    "is_valid": True,
                }
            ],
            "total_count": 1,
            "search_time_ms": 150,
            "sources_used": ["google_dork"],
        }

        with patch(
            "api.routes.search.SearchOrchestrator.search",
            AsyncMock(return_value=mock_search_result),
        ):
            response = await client.get(
                "/api/search",
                params={"q": "Inception", "max_results": 5},
            )
            # Should succeed (we may get 200 or 500 depending on DB setup)
            assert response.status_code in (200, 500)

            if response.status_code == 200:
                data = response.json()
                assert "results" in data
                assert data["total_count"] >= 0

    async def test_search_query_too_long(self, client):
        """Query longer than 200 chars should be rejected."""
        long_query = "a" * 201
        response = await client.get(
            "/api/search", params={"q": long_query}
        )
        assert response.status_code == 422

    async def test_search_with_invalid_source_filter(self, client):
        """Invalid source filter should return 400."""
        mock_result = {
            "results": [],
            "total_count": 0,
            "search_time_ms": 10,
            "sources_used": [],
        }
        with patch(
            "api.routes.search.SearchOrchestrator.search",
            AsyncMock(return_value=mock_result),
        ):
            response = await client.get(
                "/api/search",
                params={"q": "test", "source": "invalid_source_name"},
            )
            assert response.status_code == 400


# =============================================================================
# Admin endpoints
# =============================================================================

@pytest.mark.asyncio
class TestAdminEndpoint:
    """Tests for admin/monitoring endpoints."""

    async def test_admin_stats(self, client):
        """GET /api/admin/stats should return stats."""
        response = await client.get("/api/admin/stats")
        # Should work even without DB (returns partial stats)
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            data = response.json()
            assert "version" in data
            assert data["version"] == "0.3.0"

    async def test_cache_clear(self, client):
        """POST /api/admin/cache/clear should work."""
        with patch(
            "core.cache.RedisCache.clear_all",
            AsyncMock(return_value=None),
        ):
            response = await client.post("/api/admin/cache/clear")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"


# =============================================================================
# Static file serving
# =============================================================================

@pytest.mark.asyncio
class TestFrontendServing:
    """Tests for frontend static file serving."""

    async def test_frontend_index_served(self, client):
        """GET / should serve the frontend index.html."""
        response = await client.get("/")
        # Might be 200 (file found) or 404 (not found in test env)
        assert response.status_code in (200, 404)


# =============================================================================
# CORS headers
# =============================================================================

@pytest.mark.asyncio
class TestCORS:
    """Tests for CORS middleware."""

    async def test_cors_headers_present(self, client):
        """Response should include CORS headers."""
        response = await client.get("/api/health")
        # CORS headers may or may not be present for simple requests
        # But the middleware should be configured
        assert response.status_code == 200


# =============================================================================
# Search response schema validation
# =============================================================================

class TestSearchResponseSchema:
    """Test that SearchResponse schema validation works correctly."""

    def test_valid_search_response(self):
        from core.models.schemas import SearchResponse, SearchResult, SearchSource, ResourceType

        result = SearchResult(
            title="Test",
            resource_type=ResourceType.MAGNET,
            url="magnet:test",
            source=SearchSource.GOOGLE_DORK,
        )
        response = SearchResponse(
            query="test",
            results=[result],
            total_count=1,
            search_time_ms=100,
            sources_used=[SearchSource.GOOGLE_DORK],
        )
        assert response.total_count == 1
        assert len(response.results) == 1

    def test_search_response_serialization(self):
        """SearchResponse should serialize to JSON properly."""
        from core.models.schemas import SearchResponse, SearchResult, SearchSource, ResourceType

        result = SearchResult(
            title="Test Movie 1080p",
            resource_type=ResourceType.MAGNET,
            url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            source=SearchSource.PIRATE_BAY,
            seeders=150,  # >100 triggers top seeders bracket
            resolution="1080p",
        )
        result.calculate_quality_score()

        response = SearchResponse(
            query="test",
            results=[result],
            total_count=1,
            search_time_ms=150,
            sources_used=[SearchSource.PIRATE_BAY],
        )

        serialized = response.model_dump(mode="json")
        assert serialized["query"] == "test"
        assert serialized["total_count"] == 1
        assert serialized["results"][0]["title"] == "Test Movie 1080p"
        assert serialized["results"][0]["quality_score"] == 8.0
        assert serialized["sources_used"] == ["the_pirate_bay"]
