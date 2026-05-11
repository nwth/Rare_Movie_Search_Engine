"""SQLAlchemy ORM models for CineSeeker."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Movie(Base):
    """Movie metadata - stores unique movie information."""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    original_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    directors: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_count: Mapped[int] = mapped_column(Integer, default=0)
    last_searched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    resources: Mapped[list["Resource"]] = relationship(
        "Resource", back_populates="movie", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Movie {self.title} ({self.year})>"


class Resource(Base):
    """Download resource link associated with a movie."""

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("info_hash", name="uq_resource_info_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # magnet / torrent / cloud_drive / stream / ed2k
    info_hash: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # google_dork / the_pirate_bay / 1337x / yts / btdigg
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    seeders: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    leechers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    movie: Mapped["Movie"] = relationship("Movie", back_populates="resources")

    def __repr__(self) -> str:
        return f"<Resource {self.resource_type}:{self.title[:30]}>"


class SearchCache(Base):
    """Cache recent search results to avoid redundant crawling."""

    __tablename__ = "search_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    sources_used: Mapped[str] = mapped_column(String(200), nullable=True)
    search_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("query", name="uq_search_cache_query"),
    )

    def __repr__(self) -> str:
        return f"<SearchCache query={self.query}>"
