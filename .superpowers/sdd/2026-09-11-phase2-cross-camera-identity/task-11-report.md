# Task 11: Integration Test — Full Pipeline

## Status: DONE

## What was implemented

Created `tests/test_integration_phase2.py` with two integration tests:

1. **`test_full_pipeline_detection_to_footprint`** — Simulates the complete Phase 2 flow:
   - Generates two similar embeddings (simulated re-ID outputs)
   - Runs `MatchingEngine.match_or_create()` twice — first creates a new object, second matches to the same object via pgvector cosine similarity
   - Verifies both calls return the same `object_id`
   - Writes two `FootprintChainWriter` entries — verifies hash chain linkage (`entry2.previous_hash == entry1.hash`)
   - Verifies first entry has `previous_hash=None` (genesis) and correct `event_type`

2. **`test_reid_service_to_matching_engine`** — Verifies ReIDService gracefully falls back when no model is loaded, and MatchingEngine initializes with correct defaults.

## Deviations from task brief

The task brief's mock assumptions didn't match the actual source code. Adaptations made:

- **MatchingEngine**: The real code uses chained `db.query().filter().filter().all()` — not `db.execute().fetchall()`. Mock chain updated to match.
- **FootprintChainWriter**: The real code uses `db.query().filter().order_by().limit(1).all()` — the brief omitted `.limit(1)`. Mock chain updated to include it.

## Test results

```
tests/test_integration_phase2.py::test_full_pipeline_detection_to_footprint PASSED
tests/test_integration_phase2.py::test_reid_service_to_matching_engine PASSED
```

Full suite: **70 passed** in 7.52s.

## Commit

`0cd5988` — Phase 2: add integration test for full detection-to-footprint pipeline
