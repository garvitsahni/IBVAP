"""
CameraHealthStore — in-memory store for camera health status.
"""
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CameraHealthStore:
    def __init__(self):
        self._cameras: Dict[str, Dict[str, Any]] = {}

    def update(self, camera_id: str, health: Dict[str, Any]):
        self._cameras[camera_id] = {
            **health,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._cameras)

    def get(self, camera_id: str) -> Dict[str, Any]:
        return self._cameras.get(camera_id, {"status": "unknown"})

    def heartbeat(self, camera_id: str):
        """Record a heartbeat timestamp for a camera."""
        now = datetime.utcnow()
        if camera_id in self._cameras:
            self._cameras[camera_id]["last_seen"] = now
        else:
            self._cameras[camera_id] = {"status": "unknown", "last_seen": now}

    def get_last_seen(self, camera_id: str):
        """Return the last heartbeat time, or None if unknown."""
        cam = self._cameras.get(camera_id)
        if cam is None:
            return None
        return cam.get("last_seen")

    def is_stale(self, camera_id: str, threshold_seconds: int = 60) -> bool:
        """Return True if the camera hasn't heartbeat within threshold."""
        last_seen = self.get_last_seen(camera_id)
        if last_seen is None:
            return True
        elapsed = (datetime.utcnow() - last_seen).total_seconds()
        return elapsed > threshold_seconds
