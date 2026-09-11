"""CameraOfflineMonitor — detects cameras that stop sending heartbeats."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from fusion_server.services.camera_health_store import CameraHealthStore

logger = logging.getLogger(__name__)


class CameraOfflineMonitor:
    def __init__(
        self,
        store: CameraHealthStore,
        broadcaster: Any,
        ledger: Any,
        heartbeat_interval: int = 30,
        check_interval: int = 10,
        offline_threshold_multiplier: float = 2.0,
        stale_threshold_multiplier: float = 5.0,
        suppress_seconds: int = 60,
    ):
        self._store = store
        self._broadcaster = broadcaster
        self._ledger = ledger
        self._heartbeat_interval = heartbeat_interval
        self._check_interval = check_interval
        self._offline_threshold = heartbeat_interval * offline_threshold_multiplier
        self._stale_threshold = heartbeat_interval * stale_threshold_multiplier
        self._suppress_seconds = suppress_seconds
        self._last_statuses: Dict[str, str] = {}
        self._suppress_until: Dict[str, datetime] = {}
        self._task: Optional[asyncio.Task] = None

    def start(self):
        self._task = asyncio.create_task(self._run_loop())
        logger.info("CameraOfflineMonitor started")

    def stop(self):
        if self._task:
            self._task.cancel()
            logger.info("CameraOfflineMonitor stopped")

    def get_statuses(self) -> Dict[str, str]:
        result = {}
        for camera_id in self._store.get_all():
            result[camera_id] = self._compute_status(camera_id)
        return result

    def _compute_status(self, camera_id: str) -> str:
        last_seen = self._store.get_last_seen(camera_id)
        if last_seen is None:
            return "offline"
        elapsed = (datetime.utcnow() - last_seen).total_seconds()
        if elapsed > self._stale_threshold:
            return "offline"
        if elapsed > self._offline_threshold:
            return "offline"
        return "online"

    async def _run_loop(self):
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_staleness()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CameraOfflineMonitor error: {e}")

    async def _check_staleness(self):
        for camera_id in list(self._store.get_all().keys()):
            new_status = self._compute_status(camera_id)
            old_status = self._last_statuses.get(camera_id)

            if new_status != old_status:
                self._last_statuses[camera_id] = new_status
                if new_status == "offline" and old_status == "online":
                    now = datetime.utcnow()
                    suppress_until = self._suppress_until.get(camera_id, datetime.min)
                    if now < suppress_until:
                        continue
                    self._suppress_until[camera_id] = now + timedelta(seconds=self._suppress_seconds)
                    await self._broadcaster.broadcast_camera_status_changed({
                        "camera_id": camera_id,
                        "status": "offline",
                        "coverage_gaps": [],
                    })
                    logger.warning(f"Camera {camera_id} went offline")
