"""Redis cache integration for CineSeeker.

Provides fast in-memory caching layer on top of database-backed cache.
"""

import json
import logging
from typing import Optional

from config.config import settings

logger = logging.getLogger(__name__)

# Lazy-init Redis client
_redis_client = None


def get_redis():
    """Get or create the Redis async client."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            logger.info(f"Redis connected: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable (running without cache): {e}")
            _redis_client = None
    return _redis_client


async def close_redis():
    """Close the Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


class RedisCache:
    """Redis-based fast cache for search results."""

    PREFIX = "cineseeker:search:"
    TTL_SECONDS = 300  # 5 minutes (complementary to DB cache's 30 min)

    @staticmethod
    async def get(query: str) -> Optional[dict]:
        """Get cached result from Redis."""
        client = get_redis()
        if not client:
            return None

        key = f"{RedisCache.PREFIX}{query.lower().strip()}"
        try:
            data = await client.get(key)
            if data:
                logger.debug(f"Redis cache hit: '{query}'")
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Redis get failed: {e}")
        return None

    @staticmethod
    async def set(query: str, data: dict) -> None:
        """Set cached result in Redis."""
        client = get_redis()
        if not client:
            return

        key = f"{RedisCache.PREFIX}{query.lower().strip()}"
        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            await client.setex(key, RedisCache.TTL_SECONDS, serialized)
        except Exception as e:
            logger.debug(f"Redis set failed: {e}")

    @staticmethod
    async def invalidate(query: str) -> None:
        """Remove a cached entry."""
        client = get_redis()
        if not client:
            return
        key = f"{RedisCache.PREFIX}{query.lower().strip()}"
        try:
            await client.delete(key)
        except Exception:
            pass

    @staticmethod
    async def clear_all() -> None:
        """Clear all search cache entries."""
        client = get_redis()
        if not client:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor, match=f"{RedisCache.PREFIX}*", count=100
                )
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.debug(f"Redis clear failed: {e}")
