# Camera Health Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add POST endpoint for cameras to report health status and fire alerts when status is not "ok".

**Architecture:** Extend existing cameras.py router with a POST endpoint that updates CameraHealthStore and fires alerts via AlertLedger. Update FootprintEntry event_type constraint to include 'camera_compromised'.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, uuid, datetime.

## Global Constraints

- Follow existing code patterns in fusion_server/api/routes/cameras.py
- Use AlertLedger.write_alert_with_hash for alert firing (synchronous per AGENTS.md Rule 3)
- Maintain hash chain integrity for alerts
- Update FootprintEntry event_type CHECK constraint in both schema.sql and models.py
- Write tests following TDD (test first, then implement)

---

### Task 1: Write failing test for health endpoint

**Files:**
- Create: `tests/test_camera_health_alerts.py`

**Interfaces:**
- Consumes: `fusion_server.main.app` (FastAPI app)
- Produces: Test cases for POST /api/v1/cameras/{camera_id}/health

- [ ] **Step 1: Write failing test for health endpoint**

```python
# tests/test_camera_health_alerts.py
"""Tests for camera health endpoint and alert firing."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_camera_health_endpoint_updates_store():
    """POST /api/v1/cameras/{camera_id}/health updates CameraHealthStore."""
    from fusion_server.main import app
    client = TestClient(app)

    response = client.post("/api/v1/cameras/cam1/health", json={
        "status": "ok",
        "ssim": 0.87,
        "metric": None,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "cam1"
    assert data["status"] == "ok"


def test_camera_health_blinding_fires_alert():
    """POST /api/v1/cameras/cam1/health with blinding status fires alert."""
    from fusion_server.main import app
    from fusion_server.services.camera_health_store import CameraHealthStore

    client = TestClient(app)

    response = client.post("/api/v1/cameras/cam1/health", json={
        "status": "blinding",
        "ssim": 0.0,
        "metric": 5.0,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["alert_fired"] is True
    assert data["alert_reason"] == "camera_blinding"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_camera_health_alerts.py -v`
Expected: FAIL (POST /health endpoint doesn't exist)

---

### Task 2: Implement POST /health endpoint

**Files:**
- Modify: `fusion_server/api/routes/cameras.py`

**Interfaces:**
- Consumes: `CameraHealthStore.update()`, `AlertLedger.write_alert_with_hash()`
- Produces: `POST /api/v1/cameras/{camera_id}/health` endpoint

- [ ] **Step 1: Write minimal implementation**

```python
# fusion_server/api/routes/cameras.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from fusion_server.db.session import get_db
from fusion_server.services.camera_health_store import CameraHealthStore

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

# Global store instance
_health_store = CameraHealthStore()


class CameraHealthRequest(BaseModel):
    status: str  # "ok" | "blinding" | "obscured" | "frozen" | "tamper" | "drift"
    ssim: float
    metric: Optional[float] = None


class CameraHealthResponse(BaseModel):
    camera_id: str
    status: str
    ssim: float
    last_updated: str
    alert_fired: bool = False
    alert_reason: Optional[str] = None


@router.get("/health")
async def get_all_camera_health():
    """Get health status for all cameras."""
    return _health_store.get_all()


@router.post("/{camera_id}/health", response_model=CameraHealthResponse)
async def update_camera_health(
    camera_id: str,
    request: CameraHealthRequest,
    db: Session = Depends(get_db),
):
    """Update camera health status. Fires alert if status is not 'ok'."""
    _health_store.update(camera_id, {
        "status": request.status,
        "ssim": request.ssim,
        "metric": request.metric,
    })

    alert_fired = False
    alert_reason = None

    if request.status != "ok":
        # Fire camera compromised alert
        import uuid
        from fusion_server.db.models import Alert
        from fusion_server.core.alert_ledger import AlertLedger

        alert_reason = f"camera_{request.status}"
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            object_id=f"camera_{camera_id}",
            camera_id=camera_id,
            timestamp=datetime.utcnow(),
            reason=alert_reason,
            status="fired",
            threat_score=0.8,
        )
        db.add(alert)
        alert_ledger = AlertLedger()
        alert_ledger.write_alert_with_hash(db, alert)
        alert_fired = True

    return CameraHealthResponse(
        camera_id=camera_id,
        status=request.status,
        ssim=request.ssim,
        last_updated=_health_store.get(camera_id).get("last_updated", ""),
        alert_fired=alert_fired,
        alert_reason=alert_reason,
    )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_camera_health_alerts.py -v`
Expected: PASS

---

### Task 3: Update FootprintEntry event_type constraint

**Files:**
- Modify: `fusion_server/db/schema.sql`
- Modify: `fusion_server/db/models.py`

**Interfaces:**
- Consumes: None
- Produces: Updated CHECK constraint allowing 'camera_compromised' event type

- [ ] **Step 1: Update schema.sql**

```sql
-- In schema.sql:
ALTER TABLE footprint_entries DROP CONSTRAINT IF EXISTS ck_footprint_event_type;
ALTER TABLE footprint_entries ADD CONSTRAINT ck_footprint_event_type CHECK (event_type IN ('first_seen', 'hop', 'alert', 'last_seen', 'camera_compromised'));
```

- [ ] **Step 2: Update models.py CheckConstraint**

```python
# In fusion_server/db/models.py, line 58:
CheckConstraint("event_type IN ('first_seen', 'hop', 'alert', 'last_seen', 'camera_compromised')", name='ck_footprint_event_type'),
```

- [ ] **Step 3: Run all tests to verify no regressions**

Run: `.venv\Scripts\pytest tests/ -v`
Expected: All tests pass

---

### Task 4: Update ARCHITECTURE.md data contract

**Files:**
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Consumes: None
- Produces: Updated FootprintEntry event_type contract

- [ ] **Step 1: Update FootprintEntry event_type in ARCHITECTURE.md**

```markdown
### FootprintEntry (fusion server, ledger)
```json
{
  "object_id": "string",
  "camera_id": "string",
  "timestamp": "ISO8601",
  "event_type": "first_seen | hop | alert | last_seen | camera_compromised",
  "hash": "string",
  "previous_hash": "string"
}
```
```

- [ ] **Step 2: Commit ARCHITECTURE.md update**

```bash
git add ARCHITECTURE.md
git commit -m "docs: update FootprintEntry event_type contract to include camera_compromised"
```

---

### Task 5: Commit implementation

**Files:**
- Stage all modified files

**Interfaces:**
- None

- [ ] **Step 1: Stage and commit**

```bash
git add fusion_server/api/routes/cameras.py fusion_server/db/schema.sql fusion_server/db/models.py tests/test_camera_health_alerts.py
git commit -m "feat(fusion): add camera health endpoint with compromise alert firing"
```