"""WebSocket routes for real-time search progress.

Provides:
- Real-time search progress updates
- Connection-based search result delivery
- Heartbeat keepalive
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from core.search_engine import SearchOrchestrator
from core.models.schemas import SearchResponse, SearchSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections and their search states."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.search_states: dict[str, dict] = {}

    async def connect(self, ws: WebSocket) -> str:
        """Accept a WebSocket connection and return a client ID."""
        await ws.accept()
        client_id = str(uuid.uuid4())[:8]
        self.active_connections[client_id] = ws
        self.search_states[client_id] = {
            "status": "connected",
            "query": None,
            "progress": 0,
            "sources_completed": [],
            "sources_total": [],
        }
        logger.info(f"WebSocket client {client_id} connected")
        return client_id

    async def disconnect(self, client_id: str):
        """Remove a disconnected client."""
        self.active_connections.pop(client_id, None)
        self.search_states.pop(client_id, None)
        logger.info(f"WebSocket client {client_id} disconnected")

    async def send_json(self, client_id: str, data: dict):
        """Send a JSON message to a specific client."""
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                await self.disconnect(client_id)

    async def update_progress(
        self, client_id: str, status: str, progress: int,
        message: str = "", source: str = ""
    ):
        """Update and broadcast search progress."""
        state = self.search_states.get(client_id)
        if state:
            state["status"] = status
            state["progress"] = progress
            if source and source not in state["sources_completed"]:
                state["sources_completed"].append(source)

        await self.send_json(client_id, {
            "type": "progress",
            "status": status,
            "progress": progress,
            "message": message,
            "source": source,
            "sources_done": state.get("sources_completed", []) if state else [],
            "sources_total": state.get("sources_total", []) if state else [],
        })

    async def send_result(self, client_id: str, result: dict):
        """Send the final search result."""
        await self.send_json(client_id, {
            "type": "result",
            **result,
        })

    async def send_error(self, client_id: str, detail: str):
        """Send an error message."""
        await self.send_json(client_id, {
            "type": "error",
            "detail": detail,
        })

    async def heartbeat(self, client_id: str):
        """Send keepalive heartbeat."""
        await self.send_json(client_id, {"type": "heartbeat"})


manager = ConnectionManager()

# Source names for progress reporting
SEARCH_SOURCE_NAMES = {
    "google_dork": "Google Dorking",
    "the_pirate_bay": "The Pirate Bay",
    "1337x": "1337x",
    "yts": "YTS",
    "btdigg": "BTDigg",
    "quark": "夸克网盘",
    "aliyun": "阿里云盘",
    "baidu": "百度网盘",
    "dynamic": "JS动态爬虫",
}


@router.websocket("/search")
async def websocket_search(
    ws: WebSocket,
    q: str = Query(..., min_length=1, max_length=200),
    max_results: int = Query(default=30, ge=1, le=100),
):
    """WebSocket endpoint for real-time search.

    Usage:
        ws://localhost:8000/ws/search?q=Inception&max_results=30

    Progress updates are sent as JSON:
        {"type": "progress", "status": "...", "progress": 50, ...}
        {"type": "result", "results": [...], ...}
        {"type": "error", "detail": "..."}
    """
    client_id = await manager.connect(ws)
    state = manager.search_states.get(client_id, {})

    try:
        # Set up search state
        sources = list(SEARCH_SOURCE_NAMES.keys())
        state["sources_total"] = sources
        state["query"] = q

        # Notify start
        await manager.update_progress(
            client_id, "searching", 5,
            f"Starting search for '{q}'..."
        )

        # Run search
        orchestrator = SearchOrchestrator()
        total_sources = len(sources)

        # Progress: simulate search engine progress
        for i, source in enumerate(sources):
            progress = int(5 + (i / total_sources) * 85)
            source_name = SEARCH_SOURCE_NAMES.get(source, source)
            await manager.update_progress(
                client_id, "searching", progress,
                f"Searching {source_name}...", source
            )

        # Actually perform the search
        result = await orchestrator.search(q, max_results=max_results)

        # Notify completion
        await manager.update_progress(
            client_id, "completed", 100,
            f"Search complete - found {result['total_count']} results"
        )

        # Send results
        await manager.send_result(client_id, result)

        # Keep connection alive for a bit, send heartbeats
        import asyncio
        for _ in range(30):  # 30 seconds
            await asyncio.sleep(1)
            try:
                await ws.send_json({"type": "heartbeat"})
            except Exception:
                break

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.exception(f"WebSocket search error for {client_id}")
        await manager.send_error(client_id, str(e))
    finally:
        await manager.disconnect(client_id)
