# Task 2 Report: ReIDService — Person Re-ID

**Date:** 2026-09-11
**Status:** DONE

## What I Implemented

Created `edge/reid_service.py` with the `ReIDService` class that:
- Loads ONNX models for person/vehicle Re-ID inference
- Preprocesses detection crops (resize to 256×128, normalize to [0,1], NCHW format)
- Extracts embeddings via ONNX Runtime with graceful fallback when model unavailable
- Processes items from multiprocessing Queue with `(frame_id, camera_id, crop, object_type)` protocol
- Runs as a blocking service loop with shutdown signal support

## What I Tested

Created `tests/test_reid_service.py` with 4 tests:

1. **test_reid_service_initializes** — Verifies ReIDService can be instantiated with a model path
2. **test_reid_service_crop_preprocessing** — Verifies preprocessing produces correct shape (1, 3, 256, 128), dtype (float32), and value range [0, 1]
3. **test_reid_service_returns_embedding** — Verifies graceful fallback returns None when model unavailable
4. **test_reid_service_queue_protocol** — Verifies queue request/response protocol works correctly

## TDD Evidence

- **RED:** All 4 tests failed with `ModuleNotFoundError: No module named 'edge.reid_service'`
- **GREEN:** All 4 tests pass after implementation

## Test Results

```
tests/test_reid_service.py::test_reid_service_initializes PASSED
tests/test_reid_service.py::test_reid_service_crop_preprocessing PASSED
tests/test_reid_service.py::test_reid_service_returns_embedding PASSED
tests/test_reid_service.py::test_reid_service_queue_protocol PASSED

45 passed in 10.60s (full suite, no regressions)
```

## Files Changed

- `edge/reid_service.py` (created) — ReIDService implementation
- `tests/test_reid_service.py` (created) — 4 test cases

## Self-Review Findings

No concerns. Implementation:
- Follows existing patterns (DetectionService)
- Includes proper docstrings and type hints
- Handles edge cases (missing model, inference failures)
- Passes full test suite with no regressions
