# Task 9: SSE Resilience Events + Startup Integration

**Files:**
- Modify: `fusion_server/services/sse_broadcaster.py`
- Test: `tests/test_sse_resilience.py`

**Interfaces:**
- Consumes: ResilienceAggregator, CameraOfflineMonitor, DetectorFallback, PowerManager, LedgerCheckpoint
- Produces: SSE events for all resilience state changes

## Steps

### Step 1: Write the failing tests

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
async def test_broadcast_detection_tier_changed():
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

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_sse_resilience.py -v`
Expected: FAIL

### Step 3: Add resilience broadcast methods to SSEBroadcaster

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

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_sse_resilience.py -v`
Expected: 5 passed

### Step 5: Commit

```bash
git add fusion_server/services/sse_broadcaster.py tests/test_sse_resilience.py
git commit -m "feat: add resilience SSE broadcast methods"
```
