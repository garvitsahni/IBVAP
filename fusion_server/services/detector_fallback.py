"""DetectorFallback — monitors inference load and switches model tiers."""
import logging
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)

TIERS = ("normal", "degraded", "critical")
TIER_MODELS = {
    "normal": "yolov8n.pt",
    "degraded": "yolov8n.pt",  # same model, just signals degraded
    "critical": None,  # motion-only
}


class DetectorFallback:
    def __init__(
        self,
        latency_threshold_degraded: float = 200.0,
        latency_threshold_critical: float = 500.0,
        queue_threshold_degraded: int = 10,
        queue_threshold_critical: int = 30,
        error_rate_threshold: float = 0.10,
        window_size: int = 5,
        recovery_window: int = 5,
        tier_callback: Optional[Callable] = None,
    ):
        self._latency_degraded = latency_threshold_degraded
        self._latency_critical = latency_threshold_critical
        self._queue_degraded = queue_threshold_degraded
        self._queue_critical = queue_threshold_critical
        self._error_rate_threshold = error_rate_threshold
        self._window_size = window_size
        self._recovery_window = recovery_window
        self._tier_callback = tier_callback
        self._current_tier = "normal"
        self._latencies = deque(maxlen=100)
        self._queue_depths = deque(maxlen=100)
        self._error_count = 0
        self._total_count = 0
        self._consecutive_good = 0

    def get_current_tier(self) -> str:
        return self._current_tier

    def get_model_path(self) -> Optional[str]:
        return TIER_MODELS[self._current_tier]

    def report_metrics(self, latency_ms: float, queue_depth: int, errors: int):
        self._latencies.append(latency_ms)
        self._queue_depths.append(queue_depth)
        self._error_count += errors
        self._total_count += 1

        new_tier = self._evaluate_tier()
        if new_tier != self._current_tier:
            old_tier = self._current_tier
            reason = self._get_reason(new_tier)
            self._current_tier = new_tier
            self._consecutive_good = 0
            logger.warning(f"Detection tier changed: {old_tier} -> {new_tier} ({reason})")
            if self._tier_callback:
                self._tier_callback(old_tier, new_tier, reason)
        else:
            if new_tier != "normal":
                self._check_recovery()

    def _evaluate_tier(self) -> str:
        recent_latencies = list(self._latencies)[-self._window_size:]
        recent_queues = list(self._queue_depths)[-self._window_size:]
        avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0
        max_queue = max(recent_queues) if recent_queues else 0
        error_rate = self._error_count / max(self._total_count, 1)

        if (avg_latency > self._latency_critical or
            max_queue > self._queue_critical or
            error_rate > self._error_rate_threshold):
            return "critical"
        if (avg_latency > self._latency_degraded or
            max_queue > self._queue_degraded):
            return "degraded"
        return "normal"

    def _get_reason(self, tier: str) -> str:
        recent_latencies = list(self._latencies)[-self._window_size:]
        avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0
        recent_queues = list(self._queue_depths)[-self._window_size:]
        max_queue = max(recent_queues) if recent_queues else 0
        error_rate = self._error_count / max(self._total_count, 1)

        if avg_latency > self._latency_critical:
            return f"latency_{int(avg_latency)}ms_avg"
        if max_queue > self._queue_critical:
            return f"queue_{max_queue}"
        if error_rate > self._error_rate_threshold:
            return f"error_rate_{error_rate:.0%}"
        if avg_latency > self._latency_degraded:
            return f"latency_{int(avg_latency)}ms_avg"
        if max_queue > self._queue_degraded:
            return f"queue_{max_queue}"
        return "unknown"

    def _check_recovery(self):
        recent_latencies = list(self._latencies)[-self._recovery_window:]
        recent_queues = list(self._queue_depths)[-self._recovery_window:]
        if not recent_latencies:
            return
        avg_latency = sum(recent_latencies) / len(recent_latencies)
        max_queue = max(recent_queues)
        if avg_latency < self._latency_degraded and max_queue < self._queue_degraded:
            self._consecutive_good += 1
            if self._consecutive_good >= self._recovery_window:
                old_tier = self._current_tier
                self._current_tier = "normal"
                self._consecutive_good = 0
                logger.info(f"Detection recovered: {old_tier} -> normal")
                if self._tier_callback:
                    self._tier_callback(old_tier, "normal", "metrics_recovered")
        else:
            self._consecutive_good = 0