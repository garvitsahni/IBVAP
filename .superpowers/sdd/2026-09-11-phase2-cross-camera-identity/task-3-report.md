# Task 3: ReIDService — Vehicle Re-ID

## What I Implemented
Added vehicle Re-ID support to `ReIDService` per the task brief:

- `vehicle_model_path` parameter in `__init__` (default: `models/vehicle_reid.onnx`)
- `_load_vehicle_model()` method with graceful fallback on failure
- `is_vehicle` flag on `extract_embedding()` — routes to the correct model session
- `_process_one()` and `run()` now detect `object_type == "vehicle"` and pass `is_vehicle` through

## TDD Evidence

**RED:** `pytest tests/test_reid_service.py::test_reid_service_vehicle_model -v` → FAILED with `TypeError: ReIDService.__init__() got an unexpected keyword argument 'vehicle_model_path'` — expected failure before implementation.

**GREEN:** `pytest tests/test_reid_service.py -v` → 5/5 passed after implementation.

## Files Changed
- `edge/reid_service.py` — added `vehicle_model_path`, `_load_vehicle_model()`, `is_vehicle` routing
- `tests/test_reid_service.py` — added `test_reid_service_vehicle_model`

## Test Results
5/5 passing, output pristine (no stray failures; 2 deprecation warnings from FastAPI testclient, not related to this change).

## Self-Review
- All requirements from the task brief are met.
- No overbuilding — only what was specified.
- Graceful fallback preserved (returns `None` when vehicle model file doesn't exist).
- Existing tests unaffected.
