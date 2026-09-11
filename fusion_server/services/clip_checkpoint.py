"""ClipCheckpoint — tracks in-progress clip renders for crash recovery."""
import os
import logging
from typing import List

logger = logging.getLogger(__name__)


class ClipCheckpoint:
    def __init__(self, clips_dir: str = "data/clips"):
        self._dir = clips_dir
        os.makedirs(self._dir, exist_ok=True)

    def mark_pending(self, alert_id: str):
        path = os.path.join(self._dir, f"{alert_id}.pending")
        with open(path, "w") as f:
            f.write(alert_id)
        logger.debug(f"Clip pending: {alert_id}")

    def mark_complete(self, alert_id: str):
        path = os.path.join(self._dir, f"{alert_id}.pending")
        if os.path.exists(path):
            os.remove(path)
            logger.debug(f"Clip complete: {alert_id}")

    def scan_orphans(self) -> List[str]:
        result = []
        for f in os.listdir(self._dir):
            if f.endswith(".pending"):
                result.append(f.replace(".pending", ""))
        return result

    def get_incomplete(self) -> List[str]:
        return self.scan_orphans()
