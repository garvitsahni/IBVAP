## Task 4: CameraWorker — Integrate ReIDService

### What I implemented

Added ReID crop collection and embedding integration to the CameraWorker pipeline:

1. **`edge/camera_worker.py`**:
   - Added `import numpy as np` at module level
   - Added `reid_req_queue` and `reid_res_queue` parameters to `__init__`
   - Added `_crop_detection(frame, detection)` method that crops a bounding box from a frame
   - Updated `run()` loop to: send crops to ReID after tracking, collect embeddings with timeout, include embeddings when building events

2. **`edge/event_publisher.py`**:
   - Added `embedding=None` parameter to `build_event()`
   - Embedding is converted from numpy array to list via `.tolist()` if provided, else `None`

3. **`edge/run_all.py`** and **`edge/run_camera.py`**:
   - Created `reid_req_queue` and `reid_res_queue` multiprocessing queues
   - Passed them to `CameraWorker.__init__`

4. **`tests/test_camera_worker_reid.py`** (new):
   - `test_camera_worker_crops_detection`: Verifies `_crop_detection` extracts correct region
   - `test_camera_worker_sends_crop_to_reid`: Verifies crops can be placed on the ReID request queue with correct protocol

### TDD Evidence

**RED**: Tests failed with `AttributeError: 'CameraWorker' object has no attribute '_crop_detection'` — expected, feature not yet implemented.

**GREEN**: After implementation, both tests pass:
```
tests/test_camera_worker_reid.py::test_camera_worker_crops_detection PASSED
tests/test_camera_worker_reid.py::test_camera_worker_sends_crop_to_reid PASSED
```

### Test results

- 2 new tests: **2/2 passing**
- Full suite: **47/48 passing** (1 pre-existing failure in `test_reid_service_queue_protocol` from Task 2/3)

### Files changed

- `edge/camera_worker.py` — added ReID queues, `_crop_detection`, embedding collection in run loop
- `edge/event_publisher.py` — added `embedding` parameter to `build_event`
- `edge/run_all.py` — create and pass ReID queues
- `edge/run_camera.py` — create and pass ReID queues
- `tests/test_camera_worker_reid.py` — new test file

### Self-review findings

None. Implementation follows the task brief exactly, uses existing patterns, and is minimal.

### Commit

`c5fbcdc` — "Phase 2: integrate ReIDService into CameraWorker pipeline"
