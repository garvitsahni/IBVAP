"""
Publishes DetectionEvents to the fusion server via HTTP POST.
"""
import base64
import time as _time
import requests
import logging
from typing import Dict, Any, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

VEHICLE_CLASSES = {2, 3, 5, 7}


def encode_snapshot(frame, max_side: int = 640, quality: int = 80) -> Optional[str]:
    """
    Encode a BGR frame as base64 JPEG for alert thumbnails (≤640px long edge).
    Returns None on any failure — callers must treat that as 'omit the field'.
    RULE 2: this is a single still, never video.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return None
    try:
        h, w = frame.shape[:2]
        long_edge = max(h, w)
        if long_edge > max_side:
            scale = max_side / float(long_edge)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        return None


class SnapshotThrottle:
    """Allow a snapshot attach at most once per `interval` seconds."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._last = None

    def should_attach(self, now: float = None) -> bool:
        now = _time.time() if now is None else now
        if self._last is None or (now - self._last) >= self.interval:
            self._last = now
            return True
        return False


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

        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "object_type": object_type,
            "track_id": str(track_id),
            "bbox": {
                "x1": round(x1 / w, 6),
                "y1": round(y1 / h, 6),
                "x2": round(x2 / w, 6),
                "y2": round(y2 / h, 6),
            },
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
