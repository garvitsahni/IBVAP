"""
Publishes DetectionEvents to the fusion server via HTTP POST.
"""
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

VEHICLE_CLASSES = {2, 3, 5, 7}


class EventPublisher:
    """Publishes detection events to the fusion server."""

    def __init__(self, fusion_url: str, timeout: float = 2.0):
        self.fusion_url = fusion_url.rstrip("/")
        self.timeout = timeout
        self._endpoint = f"{self.fusion_url}/api/v1/events"

    def build_event(
        self,
        camera_id: str,
        timestamp: str,
        object_type: str,
        track_id: str,
        bbox_pixels: list,
        frame_shape: tuple,
        confidence: float,
        embedding=None,
    ) -> Dict[str, Any]:
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = bbox_pixels

        x_norm = x1 / w
        y_norm = y1 / h
        w_norm = (x2 - x1) / w
        h_norm = (y2 - y1) / h

        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "object_type": object_type,
            "track_id": str(track_id),
            "bbox": [round(x_norm, 6), round(y_norm, 6), round(w_norm, 6), round(h_norm, 6)],
            "embedding": embedding.tolist() if embedding is not None else None,
            "confidence": round(confidence, 4),
        }

    def publish(self, event: Dict[str, Any]) -> bool:
        try:
            resp = requests.post(
                self._endpoint,
                json=event,
                timeout=self.timeout,
            )
            if resp.status_code < 300:
                return True
            else:
                logger.warning(f"Event publish returned {resp.status_code}: {resp.text[:200]}")
                return False
        except requests.RequestException as e:
            logger.warning(f"Event publish failed (server unreachable): {e}")
            return False
