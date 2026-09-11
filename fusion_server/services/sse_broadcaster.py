"""SSE Broadcaster — pushes alerts to connected clients."""
import json
import asyncio
import logging
from typing import Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Manages SSE connections and broadcasts alerts."""

    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to alert broadcasts. Returns a queue."""
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        logger.info(f"SSE client connected. Total subscribers: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from alert broadcasts."""
        self._subscribers.discard(queue)
        logger.info(f"SSE client disconnected. Total subscribers: {len(self._subscribers)}")

    async def broadcast_alert_fired(self, alert_data) -> None:
        """Broadcast an alert_fired event to all subscribers."""
        event = {
            "event": "alert_fired",
            "data": json.dumps(alert_data if isinstance(alert_data, dict) else {
                "alert_id": alert_data.alert_id,
                "camera_id": alert_data.camera_id,
                "object_id": alert_data.object_id,
                "reason": alert_data.reason,
                "threat_score": alert_data.threat_score,
                "timestamp": alert_data.timestamp,
            }),
        }
        await self._broadcast(event)

    async def broadcast_alert_enriched(self, alert_id: str, ai_explanation: str, trajectory_projection=None) -> None:
        """Broadcast an alert_enriched event to all subscribers."""
        event = {
            "event": "alert_enriched",
            "data": json.dumps({
                "alert_id": alert_id,
                "ai_explanation": ai_explanation,
                "trajectory_projection": trajectory_projection,
            }),
        }
        await self._broadcast(event)

    async def _broadcast(self, event: dict) -> None:
        """Send event to all subscribers, removing disconnected ones."""
        dead = []
        for queue in self._subscribers:
            try:
                await queue.put(event)
            except Exception:
                dead.append(queue)
        for q in dead:
            self._subscribers.discard(q)
