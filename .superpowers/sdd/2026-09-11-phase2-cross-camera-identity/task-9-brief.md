### Task 9: API Routes — Footprint Write + Camera Health

**Files:**
- Modify: `fusion_server/api/footprint.py`
- Create: `fusion_server/api/routes/__init__.py`
- Create: `fusion_server/api/routes/cameras.py`
- Create: `tests/test_api_phase2.py`
- Modify: `fusion_server/main.py`

**Interfaces:**
- Consumes: DetectionEvents with embeddings, camera health updates
- Produces: footprint chain writes, camera health API

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_phase2.py`:
```python
"""Tests for Phase 2 API routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_footprint_write_endpoint():
    """POST /api/v1/footprint writes footprint entry."""
    from fusion_server.main import app
    client = TestClient(app)
    response = client.post("/api/v1/footprint", json={
        "object_id": "test-obj-123",
        "camera_id": "cam1",
        "timestamp": "2026-09-11T10:00:00Z",
        "event_type": "first_seen",
    })
    assert response.status_code != 404


def test_camera_health_endpoint():
    """GET /api/v1/cameras/health returns camera health status."""
    from fusion_server.main import app
    client = TestClient(app)
    response = client.get("/api/v1/cameras/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Add footprint write endpoint**

Read the existing `fusion_server/api/footprint.py` first to understand the current structure, then add the POST endpoint following the existing patterns.

- [ ] **Step 4: Create camera health route**

Create `fusion_server/api/routes/__init__.py` and `fusion_server/api/routes/cameras.py`.

- [ ] **Step 5: Register new router in main.py**

Read `fusion_server/main.py` first to understand the router registration pattern, then add the cameras router.

- [ ] **Step 6: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Run full suite**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add fusion_server/api/footprint.py fusion_server/api/routes/ fusion_server/main.py tests/test_api_phase2.py
git commit -m "Phase 2: add footprint write endpoint and camera health API"
```
