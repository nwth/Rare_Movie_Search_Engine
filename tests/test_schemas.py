"""Unit tests for Pydantic schemas and data models."""

from datetime import datetime

import pytest

from core.models.schemas import (
    MovieMetadata,
    ResourceType,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchSource,
)


class TestResourceType:
    """Tests for the ResourceType enum."""

    def test_values(self):
        assert ResourceType.MAGNET.value == "magnet"
        assert ResourceType.TORRENT.value == "torrent"
        assert ResourceType.CLOUD_DRIVE.value == "cloud_drive"
        assert ResourceType.STREAM.value == "stream"
        assert ResourceType.ED2K.value == "ed2k"

    def test_all_members(self):
        assert len(ResourceType) == 5


class TestSearchSource:
    """Tests for the SearchSource enum."""

    def test_values(self):
        assert SearchSource.GOOGLE_DORK.value == "google_dork"
        assert SearchSource.PIRATE_BAY.value == "the_pirate_bay"
        assert SearchSource.WEBSITE_1337X.value == "1337x"
        assert SearchSource.YTS.value == "yts"
        assert SearchSource.BTDIGG.value == "btdigg"
        assert SearchSource.RARBG.value == "rarbg"
        assert SearchSource.OTHER.value == "other"

    def test_all_members(self):
        assert len(SearchSource) == 7


class TestSearchResult:
    """Tests for the SearchResult model."""

    def test_minimal_creation(self):
        """A SearchResult can be created with only required fields."""
        result = SearchResult(
            title="Test Movie 1080p",
            resource_type=ResourceType.MAGNET,
            url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            source=SearchSource.GOOGLE_DORK,
        )
        assert result.title == "Test Movie 1080p"
        assert result.resource_type == ResourceType.MAGNET
        assert result.source == SearchSource.GOOGLE_DORK
        assert result.quality_score == 0.0
        assert result.is_valid is True
        assert isinstance(result.extracted_at, datetime)

    def test_full_creation(self):
        """A SearchResult can be created with all fields."""
        result = SearchResult(
            title="Test Movie 2160p",
            resource_type=ResourceType.MAGNET,
            url="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            info_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            source=SearchSource.PIRATE_BAY,
            size="2.5 GB",
            seeders=150,
            leechers=20,
            resolution="2160p",
            quality_score=5.0,
            is_valid=True,
            page_url="https://thepiratebay.org/torrent/12345",
        )
        assert result.title == "Test Movie 2160p"
        assert result.info_hash == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        assert result.seeders == 150
        assert result.resolution == "2160p"

    def test_calculate_quality_score_magnet_high_seeders(self):
        """Magnet + >100 seeders + 1080p = high score."""
        result = SearchResult(
            title="Test 1080p",
            resource_type=ResourceType.MAGNET,
            url="magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
            source=SearchSource.GOOGLE_DORK,
            seeders=150,
            resolution="1080p",
        )
        score = result.calculate_quality_score()
        # type(MAGNET)=1.0*3 + seeders(>100)=3.0 + resolution(1080p)=2.0 = 8.0
        assert score == 8.0

    def test_calculate_quality_score_low_seeders(self):
        """Few seeders + low res = lower score."""
        result = SearchResult(
            title="Test 480p",
            resource_type=ResourceType.STREAM,
            url="https://example.com/stream.mp4",
            source=SearchSource.OTHER,
            seeders=2,
            resolution="480p",
        )
        score = result.calculate_quality_score()
        # type(STREAM)=0.3*3 + seeders(2)=0.5 + resolution(480p)=0.5 = 1.9
        assert score == 1.9

    def test_calculate_quality_score_no_seeders_no_res(self):
        """No seeders or resolution = base score only."""
        result = SearchResult(
            title="Unknown",
            resource_type=ResourceType.ED2K,
            url="ed2k://test",
            source=SearchSource.OTHER,
        )
        score = result.calculate_quality_score()
        # type(ED2K)=0.5*3 = 1.5
        assert score == 1.5

    def test_quality_score_priority_magnet_over_stream(self):
        """Magnet should always rank higher than Stream with same seeders."""
        magnet = SearchResult(
            title="Magnet Test",
            resource_type=ResourceType.MAGNET,
            url="magnet:test",
            source=SearchSource.GOOGLE_DORK,
            seeders=10,
        )
        stream = SearchResult(
            title="Stream Test",
            resource_type=ResourceType.STREAM,
            url="https://stream.test",
            source=SearchSource.OTHER,
            seeders=10,
        )
        assert magnet.calculate_quality_score() > stream.calculate_quality_score()

    def test_quality_score_4k_over_1080p(self):
        """4K resolution should score higher than 1080p with same seeders."""
        uhd = SearchResult(
            title="4K Movie",
            resource_type=ResourceType.MAGNET,
            url="magnet:test",
            source=SearchSource.GOOGLE_DORK,
            seeders=50,
            resolution="2160p",
        )
        hd = SearchResult(
            title="1080p Movie",
            resource_type=ResourceType.MAGNET,
            url="magnet:test2",
            source=SearchSource.GOOGLE_DORK,
            seeders=50,
            resolution="1080p",
        )
        assert uhd.calculate_quality_score() > hd.calculate_quality_score()

    def test_is_valid_default(self):
        """is_valid should default to True."""
        result = SearchResult(
            title="Test",
            resource_type=ResourceType.MAGNET,
            url="magnet:test",
            source=SearchSource.GOOGLE_DORK,
        )
        assert result.is_valid is True


class TestSearchRequest:
    """Tests for the SearchRequest model."""

    def test_defaults(self):
        req = SearchRequest(query="Inception")
        assert req.query == "Inception"
        assert req.max_results == 30
        assert req.sources is None
        assert req.resource_type is None

    def test_min_length_validation(self):
        """query must be at least 1 character."""
        with pytest.raises(ValueError):
            SearchRequest(query="")

    def test_max_length_validation(self):
        """query must not exceed 200 characters."""
        with pytest.raises(ValueError):
            SearchRequest(query="a" * 201)

    def test_max_results_bounds(self):
        """max_results must be between 1 and 100."""
        with pytest.raises(ValueError):
            SearchRequest(query="test", max_results=0)
        with pytest.raises(ValueError):
            SearchRequest(query="test", max_results=101)


class TestMovieMetadata:
    """Tests for the MovieMetadata model."""

    def test_minimal(self):
        meta = MovieMetadata(title="Inception")
        assert meta.title == "Inception"
        assert meta.year is None
        assert meta.directors == []

    def test_full(self):
        meta = MovieMetadata(
            title="Inception",
            year=2010,
            original_title="Inception",
            directors=["Christopher Nolan"],
            imdb_id="tt1375666",
            poster_url="https://example.com/poster.jpg",
            overview="A thief who steals corporate secrets...",
        )
        assert meta.imdb_id == "tt1375666"
        assert meta.directors == ["Christopher Nolan"]

    def test_default_directors_empty_list(self):
        """directors should default to empty list, not None."""
        meta = MovieMetadata(title="Test")
        assert meta.directors == []


class TestSearchResponse:
    """Tests for the SearchResponse model."""

    def test_creation(self):
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
        assert response.query == "test"
        assert len(response.results) == 1
        assert response.total_count == 1
        assert response.movie is None

    def test_with_movie(self):
        result = SearchResult(
            title="Test",
            resource_type=ResourceType.MAGNET,
            url="magnet:test",
            source=SearchSource.GOOGLE_DORK,
        )
        movie = MovieMetadata(title="Inception", year=2010)
        response = SearchResponse(
            query="inception",
            results=[result],
            total_count=1,
            search_time_ms=200,
            sources_used=[SearchSource.GOOGLE_DORK],
            movie=movie,
        )
        assert response.movie is not None
        assert response.movie.title == "Inception"
