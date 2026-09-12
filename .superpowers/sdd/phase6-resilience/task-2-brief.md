# Task 2: CameraOfflineMonitor

**Files:**
- Create: `fusion_server/services/camera_offline_monitor.py`
- Test: `tests/test_camera_offline_monitor.py`

**Interfaces:**
- Consumes: `CameraHealthStore` (from Task 1), `SSEBroadcaster.broadcast_camera_status_changed()`, `AlertLedger.write_alert_with_hash()`
- Produces: `CameraOfflineMonitor.start()`, `.stop()`, `.get_statuses() -> Dict[str, str]`

## Steps

### Step 1: Write the failing tests

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

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_camera_offline_monitor.py -v`
Expected: FAIL — module not found

### Step 3: Implement CameraOfflineMonitor

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

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_camera_offline_monitor.py -v`
Expected: 6 passed

### Step 5: Add broadcast method to SSEBroadcaster

Edit `fusion_server/services/sse_broadcaster.py` — add method:

```python
async def broadcast_camera_status_changed(self, camera_data: dict) -> None:
    event = {
        "event": "camera_status_changed",
        "data": json.dumps(camera_data),
    }
    await self._broadcast(event)
```

### Step 6: Run all tests

Run: `pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: all pass

### Step 7: Commit

```bash
git add fusion_server/services/camera_offline_monitor.py fusion_server/services/sse_broadcaster.py tests/test_camera_offline_monitor.py
git commit -m "feat: add CameraOfflineMonitor with heartbeat timeout detection"
```
