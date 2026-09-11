### Task 4: CameraWorker — Integrate ReIDService

**Files:**
- Modify: `edge/camera_worker.py`
- Modify: `edge/event_publisher.py`

**Interfaces:**
- Consumes: detections from DetectionService, crops from frame
- Produces: DetectionEvents with `embedding` field populated

- [ ] **Step 1: Write the failing test**

Create `tests/test_camera_worker_reid.py`:
```python
"""Tests for CameraWorker Re-ID integration."""
import numpy as np
import multiprocessing
import pytest


def test_camera_worker_crops_detection():
    """CameraWorker correctly crops a detection from the frame."""
    from edge.camera_worker import CameraWorker

    # Create a mock worker (without connecting to camera)
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req = multiprocessing.Queue()
    reid_res = multiprocessing.Queue()

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = req_queue
    worker.res_queue = res_queue
    worker.reid_req_queue = reid_req
    worker.reid_res_queue = reid_res

    # Create a fake frame (480x640x3)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Fake detection: bbox in pixel coords [x1, y1, x2, y2]
    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    assert crop is not None
    assert crop.shape[2] == 3  # RGB
    assert crop.shape[0] > 0
    assert crop.shape[1] > 0


def test_camera_worker_sends_crop_to_reid():
    """CameraWorker sends crops to ReIDService queue."""
    from edge.camera_worker import CameraWorker

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req = multiprocessing.Queue()
    reid_res = multiprocessing.Queue()

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = req_queue
    worker.res_queue = res_queue
    worker.reid_req_queue = reid_req
    worker.reid_res_queue = reid_res

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    worker.reid_req_queue.put((1, "cam1", crop, "person"))

    assert not worker.reid_req_queue.empty()
    item = worker.reid_req_queue.get_nowait()
    assert item[0] == 1  # frame_id
    assert item[1] == "cam1"  # camera_id
    assert item[3] == "person"  # object_type
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_worker_reid.py -v`
Expected: FAIL (`AttributeError: CameraWorker has no attribute '_crop_detection'`)

- [ ] **Step 3: Write minimal implementation**

Modify `edge/camera_worker.py`:

Add ReID queues to `__init__`:
```python
def __init__(
    self,
    camera_url: str,
    camera_id: str,
    fusion_url: str,
    req_queue: multiprocessing.Queue,
    res_queue: multiprocessing.Queue,
    reid_req_queue: multiprocessing.Queue,
    reid_res_queue: multiprocessing.Queue,
    target_fps: int = 10,
    display: bool = True,
    force_mode: Optional[str] = None,
    mjpeg_port: int = 8081,
):
    # ... existing init ...
    self.reid_req_queue = reid_req_queue
    self.reid_res_queue = reid_res_queue
```

Add crop method:
```python
def _crop_detection(self, frame: np.ndarray, detection: dict) -> np.ndarray:
    """Crop bounding box from frame."""
    x1, y1, x2, y2 = detection["bbox"]
    h, w = frame.shape[:2]
    # Convert normalized coords to pixels if needed (already pixel coords from tracker)
    x1_int = max(0, int(x1))
    y1_int = max(0, int(y1))
    x2_int = min(w, int(x2))
    y2_int = min(h, int(y2))
    return frame[y1_int:y2_int, x1_int:x2_int].copy()
```

Update the track publishing loop to send crops to ReID:
```python
# After tracks = self.tracker.update(detections, (h, w)):
reid_embeddings = {}
for track in tracks:
    crop = self._crop_detection(frame, {"bbox": track.bbox})
    object_type = "person" if track.class_name == "person" else "vehicle"
    self.reid_req_queue.put((self._frame_id, self.camera_id, crop, object_type))

# Collect ReID results (with timeout)
for _ in range(len(tracks)):
    try:
        fid, cid, embedding, obj_type = self.reid_res_queue.get(timeout=0.2)
        if cid == self.camera_id:
            reid_embeddings[(fid, obj_type)] = embedding
    except Exception:
        continue

# When building events, include embedding
for track in tracks:
    object_type = "person" if track.class_name == "person" else "vehicle"
    embedding = reid_embeddings.get((self._frame_id, object_type))
    event = self.publisher.build_event(
        camera_id=self.camera_id,
        timestamp=ts_iso,
        object_type=object_type,
        track_id=str(track.track_id),
        bbox_pixels=track.bbox,
        frame_shape=(h, w),
        confidence=track.confidence,
        embedding=embedding,
    )
    self.publisher.publish(event)
```

- [ ] **Step 4: Update EventPublisher to accept embedding**

Modify `edge/event_publisher.py` — add `embedding` parameter to `build_event`:

```python
def build_event(
    self,
    camera_id: str,
    timestamp: str,
    object_type: str,
    track_id: str,
    bbox_pixels: list,
    frame_shape: tuple,
    confidence: float,
    embedding=None,  # NEW
) -> Dict[str, Any]:
    # ... existing bbox normalization ...
    return {
        "camera_id": camera_id,
        "timestamp": timestamp,
        "object_type": object_type,
        "track_id": str(track_id),
        "bbox": [round(x_norm, 6), round(y_norm, 6), round(w_norm, 6), round(h_norm, 6)],
        "embedding": embedding.tolist() if embedding is not None else None,  # Convert numpy to list
        "confidence": round(confidence, 4),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_worker_reid.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add edge/camera_worker.py edge/event_publisher.py tests/test_camera_worker_reid.py
git commit -m "Phase 2: integrate ReIDService into CameraWorker pipeline"
```
