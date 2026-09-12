# Task 3: Two-Tier Model Fallback + Motion Detection

**Files:**
- Create: `fusion_server/services/detector_fallback.py`
- Modify: `edge/detector.py`
- Test: `tests/test_detector_fallback.py`

**Interfaces:**
- Consumes: inference latency metrics, queue depth, error rate (from DetectionService)
- Produces: `DetectorFallback.get_current_tier()`, `.report_metrics(latency_ms, queue_depth, errors)`, `.set_tier_callback(fn)`

## Steps

### Step 1: Write the failing tests

```python
"""Tests for DetectorFallback — model tier switching."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fusion_server.services.detector_fallback import DetectorFallback


def test_fallback_initializes_at_normal():
    """DetectorFallback starts at 'normal' tier."""
    fb = DetectorFallback()
    assert fb.get_current_tier() == "normal"


def test_fallback_switches_to_degraded():
    """High latency triggers degraded tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "degraded"


def test_fallback_switches_to_critical():
    """Very high latency triggers critical tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=600, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "critical"


def test_fallback_high_queue_depth():
    """High queue depth triggers degraded tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=50, queue_depth=15, errors=0)
    assert fb.get_current_tier() == "degraded"


def test_fallback_high_error_rate():
    """High error rate triggers critical tier."""
    fb = DetectorFallback()
    for _ in range(10):
        fb.report_metrics(latency_ms=50, queue_depth=2, errors=1)
    assert fb.get_current_tier() == "critical"


def test_fallback_recovers_to_normal():
    """Good metrics after degraded triggers recovery."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "degraded"
    for _ in range(5):
        fb.report_metrics(latency_ms=50, queue_depth=2, errors=0)
    assert fb.get_current_tier() == "normal"


def test_fallback_tier_callback():
    """Tier change fires callback."""
    cb = MagicMock()
    fb = DetectorFallback(tier_callback=cb)
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    cb.assert_called_with("normal", "degraded", "latency_250ms_avg")


def test_motion_detection_returns_empty_list():
    """Motion detection on static frame returns no detections."""
    import numpy as np
    from edge.detector import motion_detection
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    prev_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    dets = motion_detection(frame, prev_frame)
    assert dets == []


def test_motion_detection_finds_movement():
    """Motion detection on different frames returns detections."""
    import numpy as np
    from edge.detector import motion_detection
    prev_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame = prev_frame.copy()
    frame[50:100, 50:100] = 255  # bright region
    dets = motion_detection(frame, prev_frame)
    assert len(dets) > 0
    assert "bbox" in dets[0]
    assert "confidence" in dets[0]
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_detector_fallback.py -v`
Expected: FAIL

### Step 3: Implement DetectorFallback

Create `fusion_server/services/detector_fallback.py`:

```python
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
```

### Step 4: Implement motion_detection in edge/detector.py

Edit `edge/detector.py` — add function at module level (after imports):

```python
def motion_detection(frame: np.ndarray, prev_frame: np.ndarray, min_area: int = 500) -> List[Dict]:
    """Frame-difference motion detection fallback."""
    import cv2
    if prev_frame is None:
        return []
    gray1 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        confidence = min(area / 10000.0, 1.0)
        detections.append({
            "bbox": [float(x), float(y), float(x + w), float(y + h)],
            "confidence": confidence,
            "class_id": 0,
            "class_name": "person",
        })
    return detections
```

Also add `set_model` method to `DetectionService` class:

```python
def set_model(self, path: str):
    """Switch to a different model weights file."""
    from ultralytics import YOLO
    logger.info(f"Switching detection model to {path}")
    self.model_path = path
    self._model = YOLO(path)
```

### Step 5: Run tests to verify they pass

Run: `pytest tests/test_detector_fallback.py -v`
Expected: 8 passed (6 fallback + 2 motion detection)

### Step 6: Commit

```bash
git add fusion_server/services/detector_fallback.py edge/detector.py tests/test_detector_fallback.py
git commit -m "feat: add two-tier model fallback with motion detection"
```
