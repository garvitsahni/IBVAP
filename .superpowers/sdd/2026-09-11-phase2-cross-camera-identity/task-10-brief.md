### Task 10: Event Ingestion — Async Matching + Footprint Write

**Files:**
- Modify: `fusion_server/api/events.py`
- Modify: `tests/test_api_phase2.py`

**Interfaces:**
- Consumes: DetectionEvents with embeddings
- Produces: async matching → footprint chain writes

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api_phase2.py`:
```python
def test_event_ingestion_triggers_matching():
    """POST /api/v1/events with embedding triggers async matching."""
    from fusion_server.main import app
    client = TestClient(app)

    import numpy as np
    embedding = np.random.rand(512).astype(float).tolist()

    response = client.post("/api/v1/events", json={
        "camera_id": "cam1",
        "timestamp": "2026-09-11T10:00:00Z",
        "object_type": "person",
        "track_id": "track_001",
        "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
        "embedding": embedding,
        "confidence": 0.95,
    })
    assert response.status_code == 201
    data = response.json()
    assert "object_id" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py::test_event_ingestion_triggers_matching -v`
Expected: FAIL (response doesn't include object_id or different status)

- [ ] **Step 3: Update event ingestion to trigger matching**

Read `fusion_server/api/events.py` first to understand current structure, then update `create_event` to:
1. Store the event in DB
2. If embedding is provided, run MatchingEngine.match_or_create
3. Update the event with the object_id
4. Write a footprint entry via FootprintChainWriter
5. Return the response with object_id

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full suite**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add fusion_server/api/events.py tests/test_api_phase2.py
git commit -m "Phase 2: add async matching and footprint write to event ingestion"
```
