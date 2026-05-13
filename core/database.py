"""Database connection and session management for CineSeeker."""

import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Engine and session factory (lazy initialized)
_engine = None
_async_session_maker = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None and settings.database_url:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_maker() -> Optional[async_sessionmaker[AsyncSession]]:
    """Get or create the async session factory."""
    global _async_session_maker
    if _async_session_maker is None and settings.database_url:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: provide an async database session."""
    session_maker = get_session_maker()
    if session_maker is None:
        logger.warning("Database not configured. Set DATABASE_URL in .env")
        yield None  # type: ignore
        return

    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup (for development).

    Gracefully handles missing database - tables are optional.
    """
    engine = get_engine()
    if engine is None:
        logger.info("No database configured, skipping table creation")
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Database unavailable, running without persistence: {e}")
        # Reset engine so subsequent calls don't retry
        global _engine
        _engine = None


async def close_db():
    """Dispose of the database engine on shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")
