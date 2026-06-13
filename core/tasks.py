"""Celery async task definitions for CineSeeker.

Handles:
- Background search processing
- Link validity checking
- Cache warming
- Periodic cleanup
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from config.config import settings

logger = logging.getLogger(__name__)

# Celery app
celery_app = Celery(
    "cineseeker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["core.tasks"],
)

# Optional Celery config
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min max per task
    task_soft_time_limit=240,
    worker_max_tasks_per_child=100,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def search_movie_task(self, query: str, max_results: int = 30):
    """Background task to search for movie resources.

    This is called when the user triggers a search via the API.
    Results are stored in Redis for retrieval via WebSocket.
    """
    import asyncio

    from core.search_engine import SearchOrchestrator

    logger.info(f"Task: Searching for '{query}'")

    try:
        # Run async search in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        orchestrator = SearchOrchestrator()
        result = loop.run_until_complete(
            orchestrator.search(query, max_results=max_results)
        )
        loop.close()

        # Store result in Redis for WebSocket delivery
        _store_result(query, result)

        logger.info(f"Task: Found {result['total_count']} results for '{query}'")
        return result

    except Exception as exc:
        logger.exception(f"Search task failed for '{query}'")
        self.retry(exc=exc)


@celery_app.task
def validate_links_task(resource_ids: list[int]):
    """Background task to validate a batch of resource links."""
    import asyncio

    from core.link_validator import LinkValidator
    from core.database import get_session_maker
    from core.models.db_models import Resource
    from sqlalchemy import select

    logger.info(f"Task: Validating {len(resource_ids)} links")

    async def _validate():
        session_maker = get_session_maker()
        if not session_maker:
            return

        async with session_maker() as session:
            for rid in resource_ids:
                result = await session.execute(
                    select(Resource).where(Resource.id == rid)
                )
                resource = result.scalar_one_or_none()
                if not resource:
                    continue

                is_valid = await LinkValidator.validate(
                    resource.url, resource.resource_type, resource.info_hash
                )
                resource.is_valid = is_valid
                resource.last_checked_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Task: Validated {len(resource_ids)} links")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_validate())
    loop.close()


@celery_app.task
def warm_cache_task(query: str):
    """Background task to pre-warm search cache for popular queries."""
    import asyncio
    from core.search_engine import SearchOrchestrator
    from core.cache import RedisCache

    logger.info(f"Task: Warming cache for '{query}'")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _warm():
        orchestrator = SearchOrchestrator()
        result = await orchestrator.search(query, max_results=30)
        await RedisCache.set(query, result)
        logger.info(f"Task: Cache warmed for '{query}' ({result['total_count']} results)")

    loop.run_until_complete(_warm())
    loop.close()


@celery_app.task
def cleanup_old_data_task():
    """Periodic cleanup of old/invalid resources and cache entries."""
    import asyncio
    from core.database import get_session_maker
    from core.services import ResourceService
    from core.models.db_models import SearchCache
    from datetime import timedelta
    from sqlalchemy import delete

    logger.info("Task: Running cleanup...")

    async def _cleanup():
        session_maker = get_session_maker()
        if not session_maker:
            return

        async with session_maker() as session:
            # Clean old invalid resources (90+ days)
            deleted = await ResourceService.clean_old_resources(session, days=90)
            logger.info(f"Cleaned {deleted} old resources")

            # Clean expired cache entries
            from sqlalchemy import select, func
            result = await session.execute(
                delete(SearchCache).where(
                    SearchCache.expires_at < datetime.now(timezone.utc)
                )
            )
            logger.info(f"Cleaned expired cache entries")

        await session.commit()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_cleanup())
    loop.close()


def _store_result(query: str, result: dict):
    """Store search result in Redis for WebSocket delivery."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        key = f"cineseeker:search_result:{query.lower().strip()}"
        r.setex(key, 300, json.dumps(result, default=str))
    except Exception as e:
        logger.debug(f"Failed to store result in Redis: {e}")


# Schedule periodic tasks
@worker_ready.connect
def at_start(sender, **kwargs):
    """Schedule periodic cleanup on worker start."""
    logger.info("Celery worker ready, scheduling periodic tasks")
    cleanup_old_data_task.delay()
