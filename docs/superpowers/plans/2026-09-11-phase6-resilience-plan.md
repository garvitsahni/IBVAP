# Phase 6 — Resilience Hardening: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the system visibly degrade instead of silently failing — camera disconnect, compute overload, crash mid-write, or power loss must produce a visible state change.

**Architecture:** Event-driven resilience bus. Independent monitors (camera offline, detector fallback, ledger checkpoint, power manager) publish health events. A `ResilienceAggregator` collects signals and pushes unified status to the dashboard via SSE.

**Tech Stack:** Python 3.13, asyncio, SQLAlchemy/PostgreSQL, psutil, cryptography (Ed25519), OpenCV, YOLOv8, React/TypeScript/TailwindCSS

## Global Constraints

- No ML alert decisions (AGENTS.md Rule 1)
- No raw video across system boundaries (Rule 2)
- Synchronous ledger writes (Rule 3)
- AI enrichment never blocks delivery (Rule 4)
- Data contracts frozen — additions only, no modifications (Rule 5)
- All resilience features validated in simulation only (Stage 3 for real hardware)
- `psutil` must be added to `requirements.txt`
- Test pattern: plain `assert`, `pytest.approx()` for floats, `@pytest.mark.asyncio` for async, docstrings on every test

---

## File Structure

| File | Purpose |
|------|---------|
| `fusion_server/services/camera_offline_monitor.py` | Heartbeat timeout + offline detection |
| `fusion_server/services/detector_fallback.py` | Model tier switching based on load |
| `fusion_server/services/ledger_checkpoint.py` | File-based checkpoint for ledger chain |
| `fusion_server/services/clip_checkpoint.py` | Pending/complete markers for clips |
| `fusion_server/services/power_manager.py` | CPU/memory monitoring + power modes |
| `fusion_server/services/model_verifier.py` | Ed25519 signature + hash verification |
| `fusion_server/services/resilience_aggregator.py` | Unified health score + SSE push |
| `fusion_server/api/routes/system.py` | `GET /api/v1/system/health` |
| `scripts/generate_model_keys.py` | Ed25519 keypair generation |
| `scripts/sign_model.py` | Model signing tool |
| `edge/model_verifier.py` | Edge-side model verification |
| `edge/detector.py` | Modify: add `set_model()` + motion detection |
| `edge/camera_worker.py` | Modify: time-based heartbeat |
| `fusion_server/services/camera_health_store.py` | Modify: add `last_seen` + heartbeat |
| `fusion_server/api/routes/cameras.py` | Modify: add heartbeat endpoint |
| `fusion_server/core/alert_ledger.py` | Modify: add checkpoint integration |
| `fusion_server/services/sse_broadcaster.py` | Modify: add resilience event broadcasts |
| `fusion_server/main.py` | Modify: register system router + startup hooks |
| `dashboard/src/components/SystemHealth.tsx` | Create: health badge + detail panel |
| `dashboard/src/components/Header.tsx` | Modify: integrate SystemHealth |
| `tests/test_camera_offline_monitor.py` | Offline monitor tests |
| `tests/test_detector_fallback.py` | Fallback logic tests |
| `tests/test_ledger_checkpoint.py` | Checkpoint write/resume tests |
| `tests/test_clip_checkpoint.py` | Clip checkpoint tests |
| `tests/test_power_manager.py` | Power manager tests |
| `tests/test_model_verifier.py` | Signature verification tests |
| `tests/test_resilience_integration.py` | End-to-end resilience tests |

---

### Task 1: Heartbeat Endpoint + CameraHealthStore Update

**Files:**
- Modify: `fusion_server/services/camera_health_store.py`
- Modify: `fusion_server/api/routes/cameras.py`
- Test: `tests/test_camera_heartbeat.py`

**Interfaces:**
- Consumes: existing `CameraHealthStore` class
- Produces: `CameraHealthStore.heartbeat(camera_id)`, `CameraHealthStore.is_stale(camera_id, threshold)`, `CameraHealthStore.get_last_seen(camera_id)`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for camera heartbeat and staleness detection."""
import pytest
from datetime import datetime, timedelta
from fusion_server.services.camera_health_store import CameraHealthStore


def test_heartbeat_updates_last_seen():
    """heartbeat() sets last_seen to current time."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    last_seen = store.get_last_seen("cam1")
    assert last_seen is not None
    assert (datetime.utcnow() - last_seen).total_seconds() < 2.0


def test_heartbeat_does_not_overwrite_health():
    """heartbeat() preserves existing health status."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok", "ssim": 0.9})
    store.heartbeat("cam1")
    health = store.get("cam1")
    assert health["status"] == "ok"
    assert health["ssim"] == 0.9


def test_is_stale_returns_false_when_recent():
    """is_stale() returns False if last_seen is within threshold."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    assert store.is_stale("cam1", threshold_seconds=60) is False


def test_is_stale_returns_true_when_old():
    """is_stale() returns True if last_seen exceeds threshold."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    # Manually backdate last_seen
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)
    assert store.is_stale("cam1", threshold_seconds=60) is True


def test_is_stale_unknown_camera():
    """is_stale() returns True for unknown cameras (never heartbeat)."""
    store = CameraHealthStore()
    assert store.is_stale("unknown_cam", threshold_seconds=60) is True


def test_get_last_seen_unknown_camera():
    """get_last_seen() returns None for unknown cameras."""
    store = CameraHealthStore()
    assert store.get_last_seen("unknown_cam") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_camera_heartbeat.py -v`
Expected: FAIL — `heartbeat`, `is_stale`, `get_last_seen` don't exist

- [ ] **Step 3: Implement CameraHealthStore changes**

Edit `fusion_server/services/camera_health_store.py` — add three methods to the existing class:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_camera_heartbeat.py -v`
Expected: 6 passed

- [ ] **Step 5: Add heartbeat endpoint to cameras.py**

Edit `fusion_server/api/routes/cameras.py` — add new endpoint after the existing health endpoint:

```python
@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, db: Session = Depends(get_db)):
    """Record a heartbeat from an edge worker."""
    store.heartbeat(camera_id)
    return {"camera_id": camera_id, "status": "ok"}
```

(Also add `from fusion_server.services.camera_health_store import CameraHealthStore` at top if not already imported, and ensure `store` is the module-level singleton.)

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add fusion_server/services/camera_health_store.py fusion_server/api/routes/cameras.py tests/test_camera_heartbeat.py
git commit -m "feat: add camera heartbeat endpoint and staleness detection"
```

---

### Task 2: CameraOfflineMonitor

**Files:**
- Create: `fusion_server/services/camera_offline_monitor.py`
- Test: `tests/test_camera_offline_monitor.py`

**Interfaces:**
- Consumes: `CameraHealthStore` (from Task 1), `SSEBroadcaster.broadcast_camera_status_changed()`, `AlertLedger.write_alert_with_hash()`
- Produces: `CameraOfflineMonitor.start()`, `.stop()`, `.get_statuses() -> Dict[str, str]`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for CameraOfflineMonitor."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from fusion_server.services.camera_health_store import CameraHealthStore
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor


@pytest.fixture
def store():
    return CameraHealthStore()


@pytest.fixture
def mock_broadcaster():
    b = MagicMock()
    b.broadcast_camera_status_changed = AsyncMock()
    return b


@pytest.fixture
def mock_ledger():
    return MagicMock()


def test_monitor_initializes():
    """CameraOfflineMonitor can be instantiated."""
    store = CameraHealthStore()
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    assert monitor is not None


def test_online_camera_not_flagged():
    """Camera with recent heartbeat is not flagged offline."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    statuses = monitor.get_statuses()
    assert statuses.get("cam1") == "online"


def test_stale_camera_flagged_offline():
    """Camera with old heartbeat is flagged offline."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    # Backdate last_seen
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
    statuses = monitor.get_statuses()
    assert statuses.get("cam1") == "offline"


def test_unknown_camera_flagged_offline():
    """Camera never seen is flagged offline."""
    store = CameraHealthStore()
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    statuses = monitor.get_statuses()
    assert statuses.get("unknown_cam") == "offline"


@pytest.mark.asyncio
async def test_check_staleness_broadcasts_offline(store, mock_broadcaster, mock_ledger):
    """check_staleness() broadcasts when camera goes offline."""
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

    monitor = CameraOfflineMonitor(store, mock_broadcaster, mock_ledger, heartbeat_interval=30)
    monitor._last_statuses = {"cam1": "online"}  # was online
    await monitor._check_staleness()

    mock_broadcaster.broadcast_camera_status_changed.assert_called_once()
    call_args = mock_broadcaster.broadcast_camera_status_changed.call_args[0][0]
    assert call_args["camera_id"] == "cam1"
    assert call_args["status"] == "offline"


@pytest.mark.asyncio
async def test_check_staleness_suppresses_repeated_offline(store, mock_broadcaster, mock_ledger):
    """Repeated offline status does not re-broadcast within suppress window."""
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

    monitor = CameraOfflineMonitor(store, mock_broadcaster, mock_ledger, heartbeat_interval=30)
    monitor._last_statuses = {"cam1": "online"}
    monitor._suppress_until = {"cam1": datetime.utcnow() + timedelta(seconds=60)}

    await monitor._check_staleness()
    mock_broadcaster.broadcast_camera_status_changed.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_camera_offline_monitor.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement CameraOfflineMonitor**

Create `fusion_server/services/camera_offline_monitor.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_camera_offline_monitor.py -v`
Expected: 6 passed

- [ ] **Step 5: Add broadcast method to SSEBroadcaster**

Edit `fusion_server/services/sse_broadcaster.py` — add method:

```python
async def broadcast_camera_status_changed(self, camera_data: dict) -> None:
    event = {
        "event": "camera_status_changed",
        "data": json.dumps(camera_data),
    }
    await self._broadcast(event)
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add fusion_server/services/camera_offline_monitor.py fusion_server/services/sse_broadcaster.py tests/test_camera_offline_monitor.py
git commit -m "feat: add CameraOfflineMonitor with heartbeat timeout detection"
```

---

### Task 3: Two-Tier Model Fallback + Motion Detection

**Files:**
- Create: `fusion_server/services/detector_fallback.py`
- Modify: `edge/detector.py`
- Test: `tests/test_detector_fallback.py`

**Interfaces:**
- Consumes: inference latency metrics, queue depth, error rate (from DetectionService)
- Produces: `DetectorFallback.get_current_tier()`, `.report_metrics(latency_ms, queue_depth, errors)`, `.set_tier_callback(fn)`

- [ ] **Step 1: Write the failing tests**

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

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_detector_fallback.py -v`
Expected: FAIL

- [ ] **Step 3: Implement DetectorFallback**

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

- [ ] **Step 4: Implement motion_detection in edge/detector.py**

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

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_detector_fallback.py -v`
Expected: 8 passed (6 fallback + 2 motion detection)

- [ ] **Step 6: Commit**

```bash
git add fusion_server/services/detector_fallback.py edge/detector.py tests/test_detector_fallback.py
git commit -m "feat: add two-tier model fallback with motion detection"
```

---

### Task 4: Ledger Checkpoint

**Files:**
- Create: `fusion_server/services/ledger_checkpoint.py`
- Test: `tests/test_ledger_checkpoint.py`

**Interfaces:**
- Consumes: alert_id, hash, chain_length
- Produces: `LedgerCheckpoint.write_checkpoint()`, `.resume()`, `.get_status()`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for LedgerCheckpoint — file-based checkpoint for ledger chain."""
import pytest
import os
import json
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint


def test_checkpoint_creates_dir(tmp_path):
    """write_checkpoint creates checkpoint directory if missing."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "checkpoints"))
    cp.write_checkpoint(alert_id=1, hash="abc123", chain_length=10)
    assert (tmp_path / "checkpoints").exists()


def test_checkpoint_writes_file(tmp_path):
    """write_checkpoint creates a JSON file."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=42, hash="def456", chain_length=156)
    files = os.listdir(str(tmp_path / "cp"))
    assert len(files) == 1
    with open(os.path.join(str(tmp_path / "cp"), files[0])) as f:
        data = json.load(f)
    assert data["last_alert_id"] == 42
    assert data["last_hash"] == "def456"
    assert data["chain_length"] == 156


def test_checkpoint_rolling_window(tmp_path):
    """Only last N checkpoints are kept."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"), max_checkpoints=3)
    for i in range(5):
        cp.write_checkpoint(alert_id=i, hash=f"hash{i}", chain_length=i)
    files = os.listdir(str(tmp_path / "cp"))
    assert len(files) == 3


def test_resume_reads_latest(tmp_path):
    """resume() reads the most recent checkpoint."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=10, hash="hash10", chain_length=10)
    cp.write_checkpoint(alert_id=20, hash="hash20", chain_length=20)
    status = cp.resume()
    assert status["last_alert_id"] == 20
    assert status["last_hash"] == "hash20"
    assert status["chain_length"] == 20


def test_resume_empty_dir(tmp_path):
    """resume() returns empty status when no checkpoints exist."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    status = cp.resume()
    assert status["status"] == "no_checkpoint"


def test_get_status_returns_last(tmp_path):
    """get_status() returns the last checkpoint info."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=5, hash="h5", chain_length=5)
    status = cp.get_status()
    assert status["status"] == "ok"
    assert status["last_alert_id"] == 5
    assert status["chain_length"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ledger_checkpoint.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LedgerCheckpoint**

Create `fusion_server/services/ledger_checkpoint.py`:

```python
"""LedgerCheckpoint — file-based checkpoint for ledger chain crash recovery."""
import json
import os
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class LedgerCheckpoint:
    def __init__(self, checkpoint_dir: str = "data/checkpoints", max_checkpoints: int = 10):
        self._dir = checkpoint_dir
        self._max = max_checkpoints
        self._last_status: Dict = {"status": "no_checkpoint"}
        os.makedirs(self._dir, exist_ok=True)

    def write_checkpoint(self, alert_id: int, hash: str, chain_length: int):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"ledger_{ts}.json"
        data = {
            "last_alert_id": alert_id,
            "last_hash": hash,
            "chain_length": chain_length,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = os.path.join(self._dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._last_status = {"status": "ok", **data}
        self._prune()
        logger.debug(f"Checkpoint written: {filename}")

    def resume(self) -> Dict:
        files = self._list_checkpoints()
        if not files:
            self._last_status = {"status": "no_checkpoint"}
            return self._last_status
        latest = files[-1]
        with open(os.path.join(self._dir, latest)) as f:
            data = json.load(f)
        self._last_status = {"status": "ok", **data}
        logger.info(f"Resumed from checkpoint: {latest} (alert_id={data['last_alert_id']})")
        return self._last_status

    def get_status(self) -> Dict:
        return dict(self._last_status)

    def _list_checkpoints(self):
        files = [f for f in os.listdir(self._dir) if f.startswith("ledger_") and f.endswith(".json")]
        files.sort()
        return files

    def _prune(self):
        files = self._list_checkpoints()
        while len(files) > self._max:
            os.remove(os.path.join(self._dir, files.pop(0)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ledger_checkpoint.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/ledger_checkpoint.py tests/test_ledger_checkpoint.py
git commit -m "feat: add LedgerCheckpoint with file-based resume"
```

---

### Task 5: Clip Checkpoint

**Files:**
- Create: `fusion_server/services/clip_checkpoint.py`
- Test: `tests/test_clip_checkpoint.py`

**Interfaces:**
- Consumes: alert_id
- Produces: `ClipCheckpoint.mark_pending()`, `.mark_complete()`, `.scan_orphans()`, `.get_incomplete()`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ClipCheckpoint — pending/complete markers for clips."""
import pytest
import os
from fusion_server.services.clip_checkpoint import ClipCheckpoint


def test_mark_pending_creates_marker(tmp_path):
    """mark_pending creates a .pending file."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-42")
    assert (tmp_path / "clips" / "alert-42.pending").exists()


def test_mark_complete_removes_marker(tmp_path):
    """mark_complete removes the .pending file."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-42")
    cp.mark_complete("alert-42")
    assert not (tmp_path / "clips" / "alert-42.pending").exists()


def test_scan_orphans_finds_pending(tmp_path):
    """scan_orphans finds .pending files."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-1")
    cp.mark_pending("alert-2")
    orphans = cp.scan_orphans()
    assert len(orphans) == 2
    assert "alert-1" in orphans
    assert "alert-2" in orphans


def test_scan_orphans_empty(tmp_path):
    """scan_orphans returns empty when no orphans."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    orphans = cp.scan_orphans()
    assert orphans == []


def test_get_incomplete(tmp_path):
    """get_incomplete returns list of incomplete alert IDs."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("a1")
    cp.mark_pending("a2")
    incomplete = cp.get_incomplete()
    assert sorted(incomplete) == ["a1", "a2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_clip_checkpoint.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ClipCheckpoint**

Create `fusion_server/services/clip_checkpoint.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_clip_checkpoint.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/clip_checkpoint.py tests/test_clip_checkpoint.py
git commit -m "feat: add ClipCheckpoint for crash-safe clip rendering"
```

---

### Task 6: Power Manager

**Files:**
- Create: `fusion_server/services/power_manager.py`
- Modify: `requirements.txt` (add psutil)
- Test: `tests/test_power_manager.py`

**Interfaces:**
- Consumes: CPU/memory metrics (via psutil)
- Produces: `PowerManager.get_mode()`, `.check_and_update()`, `.get_affected_cameras()`

- [ ] **Step 1: Add psutil to requirements.txt**

Edit `requirements.txt` — add after the existing `opencv-python-headless` line:

```
psutil>=5.9.0
```

- [ ] **Step 2: Write the failing tests**

```python
"""Tests for PowerManager — low-power fallback mode."""
import pytest
from unittest.mock import patch, MagicMock
from fusion_server.services.power_manager import PowerManager


def test_power_manager_initializes_normal():
    """PowerManager starts in 'normal' mode."""
    pm = PowerManager()
    assert pm.get_mode() == "normal"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_reduced(mock_psutil):
    """High CPU triggers 'reduced' mode."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_critical(mock_psutil):
    """Very high CPU triggers 'critical' mode."""
    mock_psutil.cpu_percent.return_value = 97.0
    mock_mem = MagicMock()
    mock_mem.percent = 95.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "critical"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_recovers(mock_psutil):
    """Low load after reduced triggers recovery to normal."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"

    mock_psutil.cpu_percent.return_value = 30.0
    mock_mem.percent = 50.0
    for _ in range(7):
        pm.check_and_update()
    assert pm.get_mode() == "normal"


def test_camera_priority_by_roi_area():
    """Cameras with larger ROI are higher priority."""
    pm = PowerManager()
    cameras = [
        {"camera_id": "cam1", "roi_area_pct": 10},
        {"camera_id": "cam2", "roi_area_pct": 50},
        {"camera_id": "cam3", "roi_area_pct": 30},
    ]
    affected = pm.get_affected_cameras(cameras, target_count=1)
    assert "cam2" not in affected  # highest priority kept
    assert "cam1" in affected  # lowest priority dropped


def test_mode_callback():
    """Mode change fires callback."""
    cb = MagicMock()
    pm = PowerManager(mode_callback=cb)
    with patch("fusion_server.services.power_manager.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 85.0
        mock_mem = MagicMock()
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem
        pm.check_and_update()
    cb.assert_called_with("normal", "reduced", "cpu_85%")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_power_manager.py -v`
Expected: FAIL

- [ ] **Step 4: Implement PowerManager**

Create `fusion_server/services/power_manager.py`:

```python
"""PowerManager — monitors system load and triggers power-saving modes."""
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None


class PowerManager:
    def __init__(
        self,
        cpu_reduced_threshold: float = 80.0,
        cpu_critical_threshold: float = 95.0,
        mem_free_reduced_pct: float = 20.0,
        mem_free_critical_pct: float = 10.0,
        recovery_threshold: float = 60.0,
        recovery_consecutive: int = 6,
        mode_callback: Optional[Callable] = None,
    ):
        self._cpu_reduced = cpu_reduced_threshold
        self._cpu_critical = cpu_critical_threshold
        self._mem_reduced = mem_free_reduced_pct
        self._mem_critical = mem_free_critical_pct
        self._recovery_threshold = recovery_threshold
        self._recovery_consecutive = recovery_consecutive
        self._mode_callback = mode_callback
        self._mode = "normal"
        self._consecutive_good = 0

    def get_mode(self) -> str:
        return self._mode

    def check_and_update(self):
        if psutil is None:
            return
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        free_pct = 100.0 - mem.percent

        new_mode = self._evaluate(cpu, free_pct)
        if new_mode != self._mode:
            old = self._mode
            reason = self._get_reason(cpu, free_pct)
            self._mode = new_mode
            self._consecutive_good = 0
            logger.warning(f"Power mode: {old} -> {new_mode} ({reason})")
            if self._mode_callback:
                self._mode_callback(old, new_mode, reason)
        elif new_mode != "normal":
            if cpu < self._recovery_threshold and free_pct > self._mem_reduced:
                self._consecutive_good += 1
                if self._consecutive_good >= self._recovery_consecutive:
                    old = self._mode
                    self._mode = "normal"
                    self._consecutive_good = 0
                    logger.info(f"Power recovered: {old} -> normal")
                    if self._mode_callback:
                        self._mode_callback(old, "normal", "load_recovered")
            else:
                self._consecutive_good = 0

    def _evaluate(self, cpu: float, free_pct: float) -> str:
        if cpu > self._cpu_critical or free_pct < self._mem_critical:
            return "critical"
        if cpu > self._cpu_reduced or free_pct < self._mem_reduced:
            return "reduced"
        return "normal"

    def _get_reason(self, cpu: float, free_pct: float) -> str:
        if cpu > self._cpu_critical:
            return f"cpu_{int(cpu)}%"
        if free_pct < self._mem_critical:
            return f"mem_{int(free_pct)}%_free"
        if cpu > self._cpu_reduced:
            return f"cpu_{int(cpu)}%"
        if free_pct < self._mem_reduced:
            return f"mem_{int(free_pct)}%_free"
        return "unknown"

    def get_affected_cameras(self, cameras: List[Dict], target_count: int) -> List[str]:
        sorted_cams = sorted(cameras, key=lambda c: c.get("roi_area_pct", 0), reverse=True)
        keep = sorted_cams[:target_count]
        drop = [c["camera_id"] for c in sorted_cams[target_count:]]
        return drop
```

- [ ] **Step 5: Install psutil**

Run: `pip install psutil>=5.9.0`
Expected: successful install

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_power_manager.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add fusion_server/services/power_manager.py requirements.txt tests/test_power_manager.py
git commit -m "feat: add PowerManager with tiered throttle modes"
```

---

### Task 7: Signed Model Packages + Verification

**Files:**
- Create: `fusion_server/services/model_verifier.py`
- Create: `edge/model_verifier.py`
- Create: `scripts/generate_model_keys.py`
- Create: `scripts/sign_model.py`
- Test: `tests/test_model_verifier.py`

**Interfaces:**
- Consumes: `.pt.signed` file (ZIP with model.pt, metadata.json, signature.bin), public key
- Produces: `ModelVerifier.verify() -> bool`, `ModelVerifier.extract_model() -> str`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ModelVerifier — Ed25519 signature + hash verification."""
import pytest
import os
import json
import hashlib
import zipfile
import tempfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fusion_server.services.model_verifier import ModelVerifier


@pytest.fixture
def keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


@pytest.fixture
def signed_model(tmp_path, keypair):
    priv_pem, pub_pem = keypair
    model_content = b"fake model weights"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test_model", "version": "1.0", "hash": model_hash}
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()

    private_key = serialization.load_pem_private_key(priv_pem, password=None)
    signature = private_key.sign(metadata_bytes)

    model_path = tmp_path / "model.pt"
    model_path.write_bytes(model_content)
    meta_path = tmp_path / "metadata.json"
    meta_path.write_text(json.dumps(metadata, sort_keys=True))
    sig_path = tmp_path / "signature.bin"
    sig_path.write_bytes(signature)

    signed_path = tmp_path / "model.pt.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.write(model_path, "model.pt")
        zf.write(meta_path, "metadata.json")
        zf.write(sig_path, "signature.bin")

    pub_key_path = tmp_path / "model_signing.pub"
    pub_key_path.write_bytes(pub_pem)

    return str(signed_path), str(pub_key_path)


def test_verify_valid_signature(signed_model):
    """Valid signature returns True."""
    signed_path, pub_key_path = signed_model
    verifier = ModelVerifier()
    assert verifier.verify(signed_path, pub_key_path) is True


def test_verify_corrupted_model(tmp_path, keypair):
    """Corrupted model (hash mismatch) returns False."""
    priv_pem, pub_pem = keypair
    model_content = b"original model"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test", "version": "1.0", "hash": model_hash}
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()
    private_key = serialization.load_pem_private_key(priv_pem, password=None)
    signature = private_key.sign(metadata_bytes)

    # Create signed package with corrupted model
    corrupted_content = b"CORRUPTED"
    signed_path = tmp_path / "bad.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.writestr("model.pt", corrupted_content)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", signature)

    pub_key_path = tmp_path / "key.pub"
    pub_key_path.write_bytes(pub_pem)

    verifier = ModelVerifier()
    assert verifier.verify(str(signed_path), str(pub_key_path)) is False


def test_verify_tampered_signature(tmp_path, keypair):
    """Tampered signature returns False."""
    priv_pem, pub_pem = keypair
    model_content = b"model data"
    model_hash = hashlib.sha256(model_content).hexdigest()
    metadata = {"name": "test", "version": "1.0", "hash": model_hash}

    signed_path = tmp_path / "bad.signed"
    with zipfile.ZipFile(signed_path, "w") as zf:
        zf.writestr("model.pt", model_content)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", b"tampered_signature_bytes")

    pub_key_path = tmp_path / "key.pub"
    pub_key_path.write_bytes(pub_pem)

    verifier = ModelVerifier()
    assert verifier.verify(str(signed_path), str(pub_key_path)) is False


def test_extract_model(signed_model):
    """extract_model writes model.pt to output path and returns it."""
    signed_path, pub_key_path = signed_model
    verifier = ModelVerifier()
    with tempfile.TemporaryDirectory() as out:
        result = verifier.extract_model(signed_path, pub_key_path, out)
        assert os.path.exists(result)
        assert result.endswith("model.pt")


def test_verify_nonexistent_file():
    """verify returns False for missing file."""
    verifier = ModelVerifier()
    assert verifier.verify("/nonexistent.signed", "/nonexistent.pub") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model_verifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ModelVerifier (server-side)**

Create `fusion_server/services/model_verifier.py`:

```python
"""ModelVerifier — Ed25519 signature + SHA-256 hash verification for model packages."""
import hashlib
import json
import logging
import os
import zipfile
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class ModelVerifier:
    def verify(self, signed_path: str, public_key_path: str) -> bool:
        if not os.path.exists(signed_path) or not os.path.exists(public_key_path):
            return False
        try:
            with zipfile.ZipFile(signed_path, "r") as zf:
                names = zf.namelist()
                if not all(n in names for n in ("model.pt", "metadata.json", "signature.bin")):
                    logger.error("Signed package missing required files")
                    return False
                model_bytes = zf.read("model.pt")
                metadata_bytes = zf.read("metadata.json")
                signature = zf.read("signature.bin")

            metadata = json.loads(metadata_bytes)
            expected_hash = metadata.get("hash", "")
            actual_hash = hashlib.sha256(model_bytes).hexdigest()
            if actual_hash != expected_hash:
                logger.error(f"Model hash mismatch: expected {expected_hash}, got {actual_hash}")
                return False

            pub_pem = open(public_key_path, "rb").read()
            public_key = serialization.load_pem_public_key(pub_pem)
            public_key.verify(signature, metadata_bytes)
            logger.info(f"Model verified: {signed_path}")
            return True
        except InvalidSignature:
            logger.error(f"Invalid signature: {signed_path}")
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    def extract_model(self, signed_path: str, public_key_path: str, output_dir: str) -> Optional[str]:
        if not self.verify(signed_path, public_key_path):
            return None
        with zipfile.ZipFile(signed_path, "r") as zf:
            zf.extract("model.pt", output_dir)
        return os.path.join(output_dir, "model.pt")
```

- [ ] **Step 4: Implement edge model_verifier.py**

Create `edge/model_verifier.py`:

```python
"""Edge-side model verification — identical logic to server ModelVerifier."""
from fusion_server.services.model_verifier import ModelVerifier

__all__ = ["ModelVerifier"]
```

- [ ] **Step 5: Implement key generation script**

Create `scripts/generate_model_keys.py`:

```python
#!/usr/bin/env python3
"""Generate Ed25519 keypair for model signing."""
import os
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "config/model_keys"
    os.makedirs(output_dir, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_path = os.path.join(output_dir, "model_signing.key")
    pub_path = os.path.join(output_dir, "model_signing.pub")

    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    os.chmod(priv_path, 0o600)
    print(f"Keys generated in {output_dir}/")
    print(f"  Private: {priv_path} (keep secret!)")
    print(f"  Public:  {pub_path} (deploy to edge)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Implement signing script**

Create `scripts/sign_model.py`:

```python
#!/usr/bin/env python3
"""Sign a YOLO model file for offline deployment."""
import hashlib
import json
import os
import sys
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def main():
    if len(sys.argv) != 4:
        print("Usage: sign_model.py <model.pt> <private_key> <output.signed>")
        sys.exit(1)

    model_path, key_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    model_bytes = open(model_path, "rb").read()
    model_hash = hashlib.sha256(model_bytes).hexdigest()

    metadata = {
        "name": os.path.basename(model_path),
        "version": "1.0",
        "hash": model_hash,
    }
    metadata_bytes = json.dumps(metadata, sort_keys=True).encode()

    private_key = serialization.load_pem_private_key(open(key_path, "rb").read(), password=None)
    signature = private_key.sign(metadata_bytes)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model.pt", model_bytes)
        zf.writestr("metadata.json", json.dumps(metadata, sort_keys=True))
        zf.writestr("signature.bin", signature)

    print(f"Signed model: {output_path}")
    print(f"  Hash: {model_hash}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_model_verifier.py -v`
Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
git add fusion_server/services/model_verifier.py edge/model_verifier.py scripts/generate_model_keys.py scripts/sign_model.py tests/test_model_verifier.py
git commit -m "feat: add Ed25519 model signing and verification"
```

---

### Task 8: Resilience Aggregator + System Health API

**Files:**
- Create: `fusion_server/services/resilience_aggregator.py`
- Create: `fusion_server/api/routes/system.py`
- Modify: `fusion_server/main.py`
- Test: `tests/test_resilience_aggregator.py`

**Interfaces:**
- Consumes: events from CameraOfflineMonitor, DetectorFallback, LedgerCheckpoint, PowerManager
- Produces: `ResilienceAggregator.get_health()`, `GET /api/v1/system/health`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ResilienceAggregator — unified system health."""
import pytest
from fusion_server.services.resilience_aggregator import ResilienceAggregator


def test_aggregator_initializes_ok():
    """Aggregator starts with 'ok' status."""
    agg = ResilienceAggregator()
    health = agg.get_health()
    assert health["status"] == "ok"


def test_aggregator_degraded_on_camera_offline():
    """Camera offline triggers 'degraded' status."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    health = agg.get_health()
    assert health["status"] == "degraded"
    assert health["cameras"]["cam1"] == "offline"


def test_aggregator_critical_on_detection_critical():
    """Critical detection tier triggers 'critical' status."""
    agg = ResilienceAggregator()
    agg.update_detection_tier("critical")
    health = agg.get_health()
    assert health["status"] == "critical"


def test_aggregator_degraded_on_power_reduced():
    """Reduced power mode triggers 'degraded' status."""
    agg = ResilienceAggregator()
    agg.update_power_mode("reduced")
    health = agg.get_health()
    assert health["status"] == "degraded"


def test_aggregator_critical_on_ledger_gap():
    """Ledger gap triggers 'critical' status."""
    agg = ResilienceAggregator()
    agg.update_ledger_status("gap_detected")
    health = agg.get_health()
    assert health["status"] == "critical"


def test_aggregator_aggregates_multiple_signals():
    """Multiple degraded signals keep worst status."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    agg.update_power_mode("reduced")
    health = agg.get_health()
    assert health["status"] == "degraded"
    assert health["cameras"]["cam1"] == "offline"
    assert health["power_mode"] == "reduced"


def test_aggregator_recovery():
    """Recovery from degraded to ok."""
    agg = ResilienceAggregator()
    agg.update_camera_status("cam1", "offline")
    assert agg.get_health()["status"] == "degraded"
    agg.update_camera_status("cam1", "online")
    assert agg.get_health()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resilience_aggregator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ResilienceAggregator**

Create `fusion_server/services/resilience_aggregator.py`:

```python
"""ResilienceAggregator — collects signals from all monitors, computes system health."""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ResilienceAggregator:
    def __init__(self):
        self._cameras: Dict[str, str] = {}
        self._detection_tier = "normal"
        self._ledger_status = "ok"
        self._power_mode = "normal"
        self._coverage_gaps = []

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
```

- [ ] **Step 4: Implement system health API**

Create `fusion_server/api/routes/system.py`:

```python
"""System health API — unified degraded mode status."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# Module-level aggregator — will be set by main.py on startup
_aggregator = None


def set_aggregator(aggregator):
    global _aggregator
    _aggregator = aggregator


@router.get("/health")
def system_health():
    if _aggregator is None:
        return {"status": "unknown", "error": "aggregator not initialized"}
    return _aggregator.get_health()
```

- [ ] **Step 5: Register router in main.py**

Edit `fusion_server/main.py` — add import and register router (near existing router imports):

```python
from fusion_server.api.routes.system import router as system_router
app.include_router(system_router)
```

Also in the startup event, initialize the aggregator:

```python
from fusion_server.services.resilience_aggregator import ResilienceAggregator
from fusion_server.api.routes.system import set_aggregator
aggregator = ResilienceAggregator()
set_aggregator(aggregator)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_resilience_aggregator.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add fusion_server/services/resilience_aggregator.py fusion_server/api/routes/system.py fusion_server/main.py tests/test_resilience_aggregator.py
git commit -m "feat: add ResilienceAggregator + GET /api/v1/system/health"
```

---

### Task 9: SSE Resilience Events + Startup Integration

**Files:**
- Modify: `fusion_server/services/sse_broadcaster.py`
- Modify: `fusion_server/main.py`
- Test: `tests/test_sse_resilience.py`

**Interfaces:**
- Consumes: ResilienceAggregator, CameraOfflineMonitor, DetectorFallback, PowerManager, LedgerCheckpoint
- Produces: SSE events for all resilience state changes

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for resilience SSE events."""
import pytest
import asyncio
import json
from fusion_server.services.sse_broadcaster import SSEBroadcaster


@pytest.mark.asyncio
async def test_broadcast_camera_status_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_camera_status_changed({"camera_id": "cam1", "status": "offline"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "camera_status_changed"
    data = json.loads(event["data"])
    assert data["camera_id"] == "cam1"


@pytest.mark.asyncio
async def def test_broadcast_detection_tier_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_detection_tier_changed({"from": "normal", "to": "degraded"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "detection_tier_changed"


@pytest.mark.asyncio
async def test_broadcast_power_mode_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_power_mode_changed({"from": "normal", "to": "reduced"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "power_mode_changed"


@pytest.mark.asyncio
async def test_broadcast_system_health_changed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_system_health_changed({"status": "degraded"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "system_health_changed"


@pytest.mark.asyncio
async def test_broadcast_ledger_resumed():
    b = SSEBroadcaster()
    q = b.subscribe()
    await b.broadcast_ledger_resumed({"status": "ok", "entries": 156})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["event"] == "ledger_resumed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sse_resilience.py -v`
Expected: FAIL

- [ ] **Step 3: Add resilience broadcast methods to SSEBroadcaster**

Edit `fusion_server/services/sse_broadcaster.py` — add these methods to the class:

```python
async def broadcast_detection_tier_changed(self, tier_data: dict) -> None:
    event = {"event": "detection_tier_changed", "data": json.dumps(tier_data)}
    await self._broadcast(event)

async def broadcast_power_mode_changed(self, power_data: dict) -> None:
    event = {"event": "power_mode_changed", "data": json.dumps(power_data)}
    await self._broadcast(event)

async def broadcast_system_health_changed(self, health_data: dict) -> None:
    event = {"event": "system_health_changed", "data": json.dumps(health_data)}
    await self._broadcast(event)

async def broadcast_ledger_resumed(self, ledger_data: dict) -> None:
    event = {"event": "ledger_resumed", "data": json.dumps(ledger_data)}
    await self._broadcast(event)
```

- [ ] **Step 4: Fix test typo (async def def → async def)**

Edit `tests/test_sse_resilience.py` line with `async def def` → `async def`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_sse_resilience.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add fusion_server/services/sse_broadcaster.py tests/test_sse_resilience.py
git commit -m "feat: add resilience SSE broadcast methods"
```

---

### Task 10: Dashboard SystemHealth Component

**Files:**
- Create: `dashboard/src/components/SystemHealth.tsx`
- Modify: `dashboard/src/components/Header.tsx`
- Modify: `dashboard/src/services/sse.ts`

**Interfaces:**
- Consumes: `GET /api/v1/system/health`, SSE `system_health_changed` event
- Produces: Health badge + expandable detail panel in Header

- [ ] **Step 1: Create SystemHealth.tsx**

Create `dashboard/src/components/SystemHealth.tsx`:

```tsx
import { useState, useEffect } from "react";

interface SystemHealth {
  status: "ok" | "degraded" | "critical" | "unknown";
  cameras: Record<string, string>;
  detection_tier: string;
  ledger: { status: string };
  power_mode: string;
}

export function SystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch("/api/v1/system/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "unknown", cameras: {}, detection_tier: "unknown", ledger: { status: "unknown" }, power_mode: "unknown" }));
  }, []);

  useEffect(() => {
    const es = new EventSource("/api/v1/stream");
    es.addEventListener("system_health_changed", (e) => {
      const data = JSON.parse(e.data);
      setHealth((prev) => prev ? { ...prev, ...data } : data);
    });
    return () => es.close();
  }, []);

  if (!health) return null;

  const statusColor = {
    ok: "bg-green-500",
    degraded: "bg-yellow-500",
    critical: "bg-red-500",
    unknown: "bg-gray-400",
  }[health.status];

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`px-3 py-1 rounded-full text-white text-sm font-medium ${statusColor}`}
      >
        {health.status.toUpperCase()}
      </button>
      {expanded && (
        <div className="absolute right-0 mt-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 p-4 text-sm">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Detection:</span>
              <span className="text-white">{health.detection_tier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Power:</span>
              <span className="text-white">{health.power_mode}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Ledger:</span>
              <span className="text-white">{health.ledger.status}</span>
            </div>
            <div className="border-t border-gray-700 pt-2 mt-2">
              <span className="text-gray-400 text-xs">Cameras:</span>
              {Object.entries(health.cameras).map(([id, status]) => (
                <div key={id} className="flex justify-between ml-2">
                  <span className="text-gray-300">{id}</span>
                  <span className={status === "online" ? "text-green-400" : "text-red-400"}>{status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Integrate SystemHealth into Header.tsx**

Edit `dashboard/src/components/Header.tsx` — import and add `<SystemHealth />` in the header bar:

```tsx
import { SystemHealth } from "./SystemHealth";
// ... in the header JSX, add:
<SystemHealth />
```

- [ ] **Step 3: Build dashboard to verify no type errors**

Run: `cd dashboard; npm run build 2>&1 | tail -10`
Expected: build succeeds

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/SystemHealth.tsx dashboard/src/components/Header.tsx
git commit -m "feat: add SystemHealth badge to dashboard header"
```

---

### Task 11: Integration Tests — Simulated Failure Scenarios

**Files:**
- Create: `tests/test_resilience_integration.py`

**Interfaces:**
- Tests the full flow: simulated failure → monitor detection → aggregator update → SSE event → dashboard state

- [ ] **Step 1: Write the integration tests**

```python
"""Phase 6 integration tests — simulated failure scenarios."""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from fusion_server.services.camera_health_store import CameraHealthStore
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor
from fusion_server.services.detector_fallback import DetectorFallback
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint
from fusion_server.services.clip_checkpoint import ClipCheckpoint
from fusion_server.services.power_manager import PowerManager
from fusion_server.services.resilience_aggregator import ResilienceAggregator


class TestCameraDisconnectSimulation:
    def test_camera_goes_offline_detected(self):
        store = CameraHealthStore()
        store.update("cam1", {"status": "ok"})
        store.heartbeat("cam1")
        store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

        monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
        statuses = monitor.get_statuses()
        assert statuses["cam1"] == "offline"

    def test_offline_updates_aggregator(self):
        store = CameraHealthStore()
        store.update("cam1", {"status": "ok"})
        store.heartbeat("cam1")
        store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

        agg = ResilienceAggregator()
        monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
        for cam_id, status in monitor.get_statuses().items():
            agg.update_camera_status(cam_id, status)
        health = agg.get_health()
        assert health["status"] == "degraded"
        assert health["cameras"]["cam1"] == "offline"


class TestComputeOverloadSimulation:
    def test_high_latency_triggers_fallback(self):
        fb = DetectorFallback()
        for _ in range(6):
            fb.report_metrics(latency_ms=300, queue_depth=5, errors=0)
        assert fb.get_current_tier() == "degraded"

    def test_extreme_load_triggers_critical(self):
        fb = DetectorFallback()
        for _ in range(6):
            fb.report_metrics(latency_ms=600, queue_depth=35, errors=0)
        assert fb.get_current_tier() == "critical"

    def test_fallback_updates_aggregator(self):
        fb = DetectorFallback()
        agg = ResilienceAggregator()
        for _ in range(6):
            fb.report_metrics(latency_ms=300, queue_depth=5, errors=0)
        agg.update_detection_tier(fb.get_current_tier())
        assert agg.get_health()["status"] == "degraded"


class TestCrashMidWriteSimulation:
    def test_checkpoint_writes_and_resumes(self, tmp_path):
        cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
        cp.write_checkpoint(alert_id=10, hash="hash10", chain_length=10)
        cp.write_checkpoint(alert_id=20, hash="hash20", chain_length=20)
        status = cp.resume()
        assert status["last_alert_id"] == 20
        assert status["chain_length"] == 20

    def test_clip_orphan_detection(self, tmp_path):
        cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
        cp.mark_pending("alert-1")
        cp.mark_pending("alert-2")
        orphans = cp.scan_orphans()
        assert len(orphans) == 2

    def test_checkpoint_updates_aggregator(self, tmp_path):
        cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
        cp.write_checkpoint(alert_id=5, hash="h5", chain_length=5)
        agg = ResilienceAggregator()
        status = cp.get_status()
        agg.update_ledger_status(status["status"])
        assert agg.get_health()["ledger"]["status"] == "ok"


class TestPowerLossSimulation:
    def test_high_cpu_triggers_reduced(self):
        with pytest.MonkeyPatch.context() as mp:
            import fusion_server.services.power_manager as pm_mod
            mock_psutil = MagicMock()
            mock_psutil.cpu_percent.return_value = 85.0
            mock_mem = MagicMock()
            mock_mem.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_mem
            mp.setattr(pm_mod, "psutil", mock_psutil)

            pm = PowerManager()
            pm.check_and_update()
            assert pm.get_mode() == "reduced"

    def test_power_mode_updates_aggregator(self):
        agg = ResilienceAggregator()
        agg.update_power_mode("reduced")
        health = agg.get_health()
        assert health["status"] == "degraded"
        assert health["power_mode"] == "reduced"


class TestEndToEndResilience:
    def test_multiple_failures_compound(self):
        agg = ResilienceAggregator()
        agg.update_camera_status("cam1", "offline")
        agg.update_detection_tier("degraded")
        agg.update_power_mode("reduced")
        health = agg.get_health()
        assert health["status"] == "degraded"

    def test_critical_status_from_any_signal(self):
        agg = ResilienceAggregator()
        agg.update_detection_tier("critical")
        assert agg.get_health()["status"] == "critical"

        agg2 = ResilienceAggregator()
        agg2.update_ledger_status("gap_detected")
        assert agg2.get_health()["status"] == "critical"

    def test_full_recovery(self):
        agg = ResilienceAggregator()
        agg.update_camera_status("cam1", "offline")
        agg.update_detection_tier("degraded")
        agg.update_power_mode("reduced")
        assert agg.get_health()["status"] == "degraded"

        agg.update_camera_status("cam1", "online")
        agg.update_detection_tier("normal")
        agg.update_power_mode("normal")
        assert agg.get_health()["status"] == "ok"
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_resilience_integration.py -v`
Expected: all passed

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: all new tests pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/test_resilience_integration.py
git commit -m "feat: add Phase 6 resilience integration tests"
```

---

### Task 12: Final Verification + Cleanup

**Files:**
- Modify: `fusion_server/main.py` (startup hooks)
- Modify: `requirements.txt` (verify psutil)

**Interfaces:**
- All monitors initialized and started on server startup
- All SSE broadcasts wired

- [ ] **Step 1: Wire all monitors into main.py startup**

Edit `fusion_server/main.py` — in the startup event, after database init:

```python
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor
from fusion_server.services.detector_fallback import DetectorFallback
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint
from fusion_server.services.clip_checkpoint import ClipCheckpoint
from fusion_server.services.power_manager import PowerManager
from fusion_server.services.resilience_aggregator import ResilienceAggregator
from fusion_server.api.routes.system import set_aggregator

# Initialize checkpoint services
ledger_cp = LedgerCheckpoint()
clip_cp = ClipCheckpoint()

# Resume ledger from checkpoint
ledger_status = ledger_cp.resume()
logger.info(f"Ledger checkpoint: {ledger_status}")

# Scan for orphaned clips
orphans = clip_cp.scan_orphans()
if orphans:
    logger.warning(f"Found {len(orphans)} orphaned clip(s): {orphans}")

# Initialize aggregator
aggregator = ResilienceAggregator()
aggregator.update_ledger_status(ledger_status.get("status", "ok"))
set_aggregator(aggregator)

# Initialize monitors (will be started by their respective owners)
detector_fallback = DetectorFallback()
power_manager = PowerManager()
```

- [ ] **Step 2: Run full test suite one final time**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: all tests pass

- [ ] **Step 3: Build dashboard**

Run: `cd dashboard; npm run build 2>&1 | tail -5`
Expected: build succeeds

- [ ] **Step 4: Final commit**

```bash
git add fusion_server/main.py
git commit -m "feat: wire all Phase 6 resilience monitors into server startup"
```

---

*Plan complete. All 12 tasks with full code, tests, and commits. Ready for execution.*
