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

    async def broadcast_camera_status_changed(self, camera_data: dict) -> None:
        """Broadcast a camera_status_changed event to all subscribers."""
        event = {
            "event": "camera_status_changed",
            "data": json.dumps(camera_data),
        }
        await self._broadcast(event)

    async def broadcast_detection_tier_changed(self, tier_data: dict) -> None:
        """Broadcast a detection_tier_changed event to all subscribers."""
        event = {"event": "detection_tier_changed", "data": json.dumps(tier_data)}
        await self._broadcast(event)

    async def broadcast_power_mode_changed(self, power_data: dict) -> None:
        """Broadcast a power_mode_changed event to all subscribers."""
        event = {"event": "power_mode_changed", "data": json.dumps(power_data)}
        await self._broadcast(event)

    async def broadcast_system_health_changed(self, health_data: dict) -> None:
        """Broadcast a system_health_changed event to all subscribers."""
        event = {"event": "system_health_changed", "data": json.dumps(health_data)}
        await self._broadcast(event)

    async def broadcast_ledger_resumed(self, ledger_data: dict) -> None:
        """Broadcast a ledger_resumed event to all subscribers."""
        event = {"event": "ledger_resumed", "data": json.dumps(ledger_data)}
        await self._broadcast(event)

    async def broadcast_detection(self, detection_data: dict) -> None:
        """Broadcast a detection event to all subscribers."""
        event = {"event": "detection", "data": json.dumps(detection_data)}
        await self._broadcast(event)

    async def broadcast_plate_read(self, plate_data: dict) -> None:
        """Broadcast a plate_read event when ANPR reads a plate."""
        event = {"event": "plate_read", "data": json.dumps(plate_data)}
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
