### Task 11: Integration Test — Full Pipeline

**Files:**
- Create: `tests/test_integration_phase2.py`

**Interfaces:**
- Consumes: all Phase 2 components
- Produces: end-to-end verification

- [ ] **Step 1: Write the failing test**

Create `tests/test_integration_phase2.py`:
```python
"""Integration test for Phase 2 — full pipeline from detection to footprint chain."""
import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def test_full_pipeline_detection_to_footprint():
    """
    Simulate: detection → embedding → matching → footprint chain.
    This verifies the complete Phase 2 flow.
    """
    from fusion_server.services.matching_engine import MatchingEngine
    from fusion_server.services.footprint_writer import FootprintChainWriter

    embedding1 = np.random.rand(512).astype(np.float32)
    embedding1 = embedding1 / np.linalg.norm(embedding1)

    embedding2 = embedding1 + np.random.randn(512).astype(np.float32) * 0.01
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    engine = MatchingEngine(threshold_person=0.5)
    mock_db = MagicMock()

    mock_db.execute.return_value.fetchall.return_value = []
    object_id1 = engine.match_or_create(
        db=mock_db,
        embedding=embedding1,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
    )

    mock_result = MagicMock()
    mock_result.object_id = object_id1
    mock_result.distance = 0.01
    mock_db.execute.return_value.fetchall.return_value = [mock_result]

    object_id2 = engine.match_or_create(
        db=mock_db,
        embedding=embedding2,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
    )

    assert object_id1 == object_id2, "Same object should get same object_id"

    writer = FootprintChainWriter()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    entry1 = writer.write_entry(
        db=mock_db,
        object_id=object_id1,
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
        event_type="first_seen",
        detection_event_id=1,
    )

    assert entry1 is not None
    assert entry1["event_type"] == "first_seen"
    assert entry1["previous_hash"] is None

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = entry1["hash"]
    mock_last_entry.timestamp = datetime(2026, 9, 11, 10, 0, 0)
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_last_entry]

    entry2 = writer.write_entry(
        db=mock_db,
        object_id=object_id1,
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
        event_type="hop",
        detection_event_id=2,
    )

    assert entry2 is not None
    assert entry2["event_type"] == "hop"
    assert entry2["previous_hash"] == entry1["hash"]


def test_reid_service_to_matching_engine():
    """Verify ReIDService output feeds into MatchingEngine."""
    from edge.reid_service import ReIDService
    from fusion_server.services.matching_engine import MatchingEngine

    req_queue = MagicMock()
    res_queue = MagicMock()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop)
    assert embedding is None

    engine = MatchingEngine()
    assert engine.threshold_person == 0.65
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_integration_phase2.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Run full suite**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_phase2.py
git commit -m "Phase 2: add integration test for full detection-to-footprint pipeline"
```
