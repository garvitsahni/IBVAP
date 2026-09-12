# Task 1: Heartbeat Endpoint + CameraHealthStore Update

**Files:**
- Modify: `fusion_server/services/camera_health_store.py`
- Modify: `fusion_server/api/routes/cameras.py`
- Test: `tests/test_camera_heartbeat.py`

**Interfaces:**
- Consumes: existing `CameraHealthStore` class
- Produces: `CameraHealthStore.heartbeat(camera_id)`, `CameraHealthStore.is_stale(camera_id, threshold)`, `CameraHealthStore.get_last_seen(camera_id)`

## Steps

### Step 1: Write the failing tests

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

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_camera_heartbeat.py -v`
Expected: FAIL — `heartbeat`, `is_stale`, `get_last_seen` don't exist

### Step 3: Implement CameraHealthStore changes

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

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_camera_heartbeat.py -v`
Expected: 6 passed

### Step 5: Add heartbeat endpoint to cameras.py

Edit `fusion_server/api/routes/cameras.py` — add new endpoint after the existing health endpoint:

```python
@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, db: Session = Depends(get_db)):
    """Record a heartbeat from an edge worker."""
    store.heartbeat(camera_id)
    return {"camera_id": camera_id, "status": "ok"}
```

(Also add `from fusion_server.services.camera_health_store import CameraHealthStore` at top if not already imported, and ensure `store` is the module-level singleton.)

### Step 6: Run full test suite to verify no regressions

Run: `pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all existing tests still pass

### Step 7: Commit

```bash
git add fusion_server/services/camera_health_store.py fusion_server/api/routes/cameras.py tests/test_camera_heartbeat.py
git commit -m "feat: add camera heartbeat endpoint and staleness detection"
```
