"""Pydantic schemas for CineSeeker data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Priority: Magnet > CloudDrive > Stream."""

    MAGNET = "magnet"
    TORRENT = "torrent"
    CLOUD_DRIVE = "cloud_drive"
    STREAM = "stream"
    ED2K = "ed2k"


class SearchSource(str, Enum):
    """Source of the search result."""

    GOOGLE_DORK = "google_dork"
    PIRATE_BAY = "the_pirate_bay"
    WEBSITE_1337X = "1337x"
    YTS = "yts"
    BTDIGG = "btdigg"
    RARBG = "rarbg"
    OTHER = "other"


class SearchResult(BaseModel):
    """A single search result item (a downloadable resource)."""

    title: str
    resource_type: ResourceType
    url: str
    info_hash: Optional[str] = None
    source: SearchSource
    size: Optional[str] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    resolution: Optional[str] = None
    quality_score: float = 0.0
    is_valid: bool = True
    page_url: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    def calculate_quality_score(self) -> float:
        """Calculate quality score based on seeders, resolution & resource type."""
        score = 0.0

        # Resource type priority
        type_scores = {
            ResourceType.MAGNET: 1.0,
            ResourceType.TORRENT: 0.9,
            ResourceType.CLOUD_DRIVE: 0.7,
            ResourceType.ED2K: 0.5,
            ResourceType.STREAM: 0.3,
        }
        score += type_scores.get(self.resource_type, 0.0) * 3

        # Seeders bonus
        if self.seeders is not None:
            if self.seeders > 100:
                score += 3.0
            elif self.seeders > 50:
                score += 2.0
            elif self.seeders > 10:
                score += 1.0
            elif self.seeders > 0:
                score += 0.5

        # Resolution bonus
        if self.resolution:
            res_scores = {
                "2160p": 3.0,
                "4K": 3.0,
                "1080p": 2.0,
                "720p": 1.0,
                "480p": 0.5,
            }
            for key, val in res_scores.items():
                if key in self.resolution:
                    score += val
                    break

        self.quality_score = round(score, 2)
        return self.quality_score


class SearchRequest(BaseModel):
    """Incoming search request from user."""

    query: str = Field(..., min_length=1, max_length=200, description="Movie name or keywords")
    sources: Optional[list[SearchSource]] = None
    max_results: int = Field(default=30, ge=1, le=100)
    resource_type: Optional[ResourceType] = None


class ImageSearchRequest(BaseModel):
    """Incoming image search request."""

    image_url: Optional[str] = None
    # For future: base64 encoded image


class MovieMetadata(BaseModel):
    """Movie metadata extracted from image search or TMDb."""

    title: str
    year: Optional[int] = None
    original_title: Optional[str] = None
    directors: list[str] = []
    imdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    overview: Optional[str] = None


class SearchResponse(BaseModel):
    """Response returned to the user."""

    query: str
    movie: Optional[MovieMetadata] = None
    results: list[SearchResult]
    total_count: int
    search_time_ms: int
    sources_used: list[SearchSource]
