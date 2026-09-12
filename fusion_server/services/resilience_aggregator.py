"""ResilienceAggregator — collects signals from all monitors, computes system health."""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ResilienceAggregator:
    def __init__(self):
        self._cameras: Dict[str, str] = {}
        self._detection_tier = "normal"
        self._ledger_status = "ok"
        self._power_mode = "normal"
        self._coverage_gaps: List = []

    def get_health(self) -> Dict:
        status = self._compute_status()
        return {
            "status": status,
            "cameras": dict(self._cameras),
            "coverage_gaps": list(self._coverage_gaps),
            "detection_tier": self._detection_tier,
            "ledger": {"status": self._ledger_status},
            "power_mode": self._power_mode,
        }

    def update_camera_status(self, camera_id: str, status: str):
        self._cameras[camera_id] = status

    def update_detection_tier(self, tier: str):
        self._detection_tier = tier

    def update_ledger_status(self, status: str):
        self._ledger_status = status

    def update_power_mode(self, mode: str):
        self._power_mode = mode

    def update_coverage_gaps(self, gaps):
        self._coverage_gaps = gaps

    def _compute_status(self) -> str:
        if self._detection_tier == "critical":
            return "critical"
        if self._ledger_status == "gap_detected":
            return "critical"
        if self._power_mode == "critical":
            return "critical"
        offline_count = sum(1 for s in self._cameras.values() if s == "offline")
        if offline_count >= 2:
            return "critical"
        if self._detection_tier != "normal":
            return "degraded"
        if self._power_mode != "normal":
            return "degraded"
        if offline_count > 0:
            return "degraded"
        return "ok"
