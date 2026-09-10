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
