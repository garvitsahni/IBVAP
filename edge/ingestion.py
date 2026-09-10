"""
RTSP stream reader with retry logic.
"""
import cv2
import time
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class RTSPIngestion:
    """Reads frames from an RTSP stream with automatic reconnection."""

    def __init__(self, url: str, max_retries: int = 3, retry_delay: float = 2.0):
        self.url = url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        for attempt in range(self.max_retries):
            try:
                self._cap = cv2.VideoCapture(self.url)
                if self._cap.isOpened():
                    logger.info(f"Connected to {self.url}")
                    return True
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: Cannot open {self.url}")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {e}")
            time.sleep(self.retry_delay)

        logger.error(f"Failed to connect to {self.url} after {self.max_retries} attempts")
        return False

    def grab_frame(self) -> Optional[Tuple[datetime, object]]:
        if self._cap is None or not self._cap.isOpened():
            if not self.connect():
                return None

        ret, frame = self._cap.read()
        if not ret:
            logger.warning(f"Failed to read frame from {self.url}, reconnecting...")
            self.release()
            if self.connect():
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None

        timestamp = datetime.utcnow()
        return timestamp, frame

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __del__(self):
        self.release()
