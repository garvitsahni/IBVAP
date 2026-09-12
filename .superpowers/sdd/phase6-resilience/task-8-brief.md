# Task 8: Resilience Aggregator + System Health API

**Files:**
- Create: `fusion_server/services/resilience_aggregator.py`
- Create: `fusion_server/api/routes/system.py`
- Modify: `fusion_server/main.py`
- Test: `tests/test_resilience_aggregator.py`

**Interfaces:**
- Consumes: events from CameraOfflineMonitor, DetectorFallback, LedgerCheckpoint, PowerManager
- Produces: `ResilienceAggregator.get_health()`, `GET /api/v1/system/health`

## Steps

### Step 1: Write the failing tests

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

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_resilience_aggregator.py -v`
Expected: FAIL

### Step 3: Implement ResilienceAggregator

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

### Step 4: Implement system health API

Create `fusion_server/api/routes/system.py`:

```python
"""System health API — unified degraded mode status."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/system", tags=["system"])

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

### Step 5: Register router in main.py

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

### Step 6: Run tests to verify they pass

Run: `pytest tests/test_resilience_aggregator.py -v`
Expected: 7 passed

### Step 7: Commit

```bash
git add fusion_server/services/resilience_aggregator.py fusion_server/api/routes/system.py fusion_server/main.py tests/test_resilience_aggregator.py
git commit -m "feat: add ResilienceAggregator and system health API"
```
