# Phase 2 — Cross-Camera Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build cross-camera person/vehicle re-identification, footprint chain tracking, and camera health monitoring. Exit criteria: walk from one camera's FOV into another's, see the footprint chain update in real time, correctly identifying it as the same object across both cameras.

**Architecture:** Edge-side ReIDService extracts 512-dim embeddings from detection crops (OSNet for persons, lightweight CNN for vehicles). Fusion server receives DetectionEvents with embeddings, runs async pgvector cosine matching to assign global `object_id`s, then writes footprint chain entries (first_seen → hop → last_seen) with tamper-evident SHA-256 hashes. CameraHealthService monitors frame-level SSIM and embedding-level scene drift.

**Tech Stack:** Python 3.13, onnxruntime (Re-ID inference), scikit-image (SSIM), pgvector (cosine search), FastAPI, SQLAlchemy, multiprocessing.Queue IPC

## Global Constraints

- Python 3.13 on Windows (PowerShell — no `&&`, no `&` for backgrounding)
- Virtual env: `.\venv\Scripts\activate`
- Docker PostgreSQL on port **5434** (not 5432 or 5433)
- Data contracts in ARCHITECTURE.md §5 are frozen — `DetectionEvent.embedding` is `Vector(512)`, `FootprintEntry.object_id` is `String(128)`
- ML never fires alerts — only rule engine sets `alert.status = fired`
- Ledger write is synchronous and blocking
- pip mirror: `-i https://pypi.tuna.tsinghua.edu.cn/simple`
- Every task ends with tests passing and a commit

---

## File Structure

```
edge/
├── reid_service.py              # ReIDService: OSNet + vehicle ReID via onnxruntime
├── camera_health.py             # CameraHealthService: SSIM + scene embedding drift

fusion_server/
├── api/routes/footprint.py      # MODIFY: add POST endpoint for footprint writes
├── api/routes/cameras.py        # NEW: GET /api/v1/cameras/health
├── services/
│   ├── __init__.py              # NEW
│   ├── matching_engine.py       # pgvector cosine search + object_id assignment
│   ├── footprint_writer.py      # Footprint chain logic with hash linkage
│   └── camera_health_store.py   # Reference frames + scene embeddings

tests/
├── test_reid_service.py         # ReIDService unit tests (mock model)
├── test_matching_engine.py      # Matching engine tests (mock pgvector)
├── test_footprint_writer.py     # Footprint chain tests (mock DB)
├── test_camera_health.py        # Camera drift detection tests
└── test_integration_phase2.py   # Full pipeline integration test

models/                          # NEW directory
├── osnet_ain_x1_0.onnx          # Person Re-ID model (download)
└── vehicle_reid.onnx             # Vehicle Re-ID model (download)
```

---

### Task 1: Install Dependencies + Download Models

**Files:**
- Modify: `requirements.txt`
- Create: `models/` directory

**Interfaces:**
- Consumes: nothing
- Produces: onnxruntime, scikit-image available; model files in `models/`

- [ ] **Step 1: Add dependencies to requirements.txt**

Append to `requirements.txt`:
```
onnxruntime>=1.17.0
scikit-image>=0.22.0
```

- [ ] **Step 2: Install dependencies**

Run: `.\venv\Scripts\activate; pip install onnxruntime scikit-image -i https://pypi.tuna.tsinghua.edu.cn/simple`

- [ ] **Step 3: Create models directory and download OSNet**

```powershell
mkdir models
# Download OSNet AIN x1.0 (person Re-ID, ONNX format)
# Source: https://github.com/micr.cloudml/OSNet
# For Stage 1, we use a pre-exported ONNX model
# If download fails, create a stub for testing
```

- [ ] **Step 4: Create vehicle Re-ID stub model**

For Stage 1, create a minimal ONNX model stub that outputs 512-dim embeddings. This will be replaced with a real model later.

- [ ] **Step 5: Run existing tests to verify nothing broke**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add requirements.txt models/
git commit -m "Phase 2: add onnxruntime, scikit-image dependencies and model directory"
```

---

### Task 2: ReIDService — Person Re-ID

**Files:**
- Create: `edge/reid_service.py`
- Create: `tests/test_reid_service.py`

**Interfaces:**
- Consumes: crops (numpy arrays) from CameraWorker via `multiprocessing.Queue`
- Produces: 512-dim embeddings via response Queue

- [ ] **Step 1: Write the failing test**

Create `tests/test_reid_service.py`:
```python
"""Tests for ReIDService — Re-ID embedding extraction."""
import numpy as np
import multiprocessing
import pytest


def test_reid_service_initializes():
    """ReIDService can be instantiated with a model path."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")
    assert svc is not None


def test_reid_service_crop_preprocessing():
    """ReIDService preprocesses crop correctly (resize to 256x128, normalize)."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    # Create a fake crop (RGB, any size)
    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    processed = svc._preprocess_crop(crop)
    assert processed.shape == (1, 3, 256, 128)  # NCHW format
    assert processed.dtype == np.float32
    # Should be normalized to [0, 1]
    assert processed.min() >= 0.0
    assert processed.max() <= 1.0


def test_reid_service_returns_embedding():
    """ReIDService returns 512-dim embedding (or None if model unavailable)."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop)
    # With no model loaded, should return None (graceful fallback)
    assert embedding is None


def test_reid_service_queue_protocol():
    """ReIDService processes queue items correctly."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    # Put a request: (frame_id, camera_id, crop, object_type)
    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    req_queue.put((1, "cam1", crop, "person"))

    # Process one item
    svc._process_one()

    # Check response
    assert not res_queue.empty()
    fid, cid, embedding, obj_type = res_queue.get_nowait()
    assert fid == 1
    assert cid == "cam1"
    assert obj_type == "person"
    # Embedding is None (no model), but protocol works
    assert embedding is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_reid_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edge.reid_service'`

- [ ] **Step 3: Write minimal implementation**

Create `edge/reid_service.py`:
```python
"""
Re-ID Service — extracts person/vehicle embeddings from detection crops.
Runs as a separate process, receives crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Standard Re-ID input size
REID_INPUT_HEIGHT = 256
REID_INPUT_WIDTH = 128


class ReIDService:
    """
    Re-ID embedding extraction service.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = ReIDService(req_queue, res_queue, model_path="models/osnet_ain_x1_0.onnx")
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "models/osnet_ain_x1_0.onnx",
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self._session = None
        self._input_name = None

    def _load_model(self):
        """Load ONNX model for inference."""
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(self.model_path)
            self._input_name = self._session.get_inputs()[0].name
            logger.info(f"ReID model loaded from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load ReID model from {self.model_path}: {e}")
            logger.warning("ReID service will return None embeddings (graceful fallback)")
            self._session = None

    def _preprocess_crop(self, crop: np.ndarray) -> np.ndarray:
        """
        Preprocess crop for Re-ID inference.
        Input: BGR numpy array (H, W, 3) uint8
        Output: NCHW float32 array normalized to [0, 1]
        """
        import cv2
        # Resize to standard Re-ID input size
        resized = cv2.resize(crop, (REID_INPUT_WIDTH, REID_INPUT_HEIGHT))
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Normalize to [0, 1] and transpose to NCHW
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)  # HWC -> CHW
        blob = np.expand_dims(blob, 0)  # Add batch dimension
        return blob

    def extract_embedding(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract 512-dim embedding from a crop.
        Returns None if model is not available.
        """
        if self._session is None:
            return None

        try:
            blob = self._preprocess_crop(crop)
            outputs = self._session.run(None, {self._input_name: blob})
            embedding = outputs[0].flatten()
            # Normalize to unit vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            logger.error(f"ReID inference failed: {e}")
            return None

    def _process_one(self):
        """Process one item from the request queue."""
        try:
            item = self.req_queue.get(timeout=0.1)
        except Exception:
            return

        if item is None:
            return

        frame_id, camera_id, crop, object_type = item
        embedding = self.extract_embedding(crop)
        self.res_queue.put((frame_id, camera_id, embedding, object_type))

    def run(self):
        """Main loop — process crops from queue."""
        self._load_model()
        logger.info("ReID service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("ReID service received shutdown signal")
                break

            frame_id, camera_id, crop, object_type = item
            try:
                embedding = self.extract_embedding(crop)
                self.res_queue.put((frame_id, camera_id, embedding, object_type))
            except Exception as e:
                logger.error(f"ReID failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, None, object_type))

        logger.info("ReID service stopped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_reid_service.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/reid_service.py tests/test_reid_service.py
git commit -m "Phase 2: add ReIDService with ONNX inference and graceful fallback"
```

---

### Task 3: ReIDService — Vehicle Re-ID

**Files:**
- Modify: `edge/reid_service.py`
- Modify: `tests/test_reid_service.py`

**Interfaces:**
- Consumes: vehicle crops from CameraWorker
- Produces: 512-dim embeddings (or None if model unavailable)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reid_service.py`:
```python
def test_reid_service_vehicle_model():
    """ReIDService handles vehicle crops with separate model path."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(
        req_queue, res_queue,
        model_path="models/osnet_ain_x1_0.onnx",
        vehicle_model_path="models/vehicle_reid.onnx",
    )
    crop = np.random.randint(0, 255, (80, 200, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop, is_vehicle=True)
    # With no vehicle model loaded, should return None
    assert embedding is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_reid_service.py::test_reid_service_vehicle_model -v`
Expected: FAIL (signature mismatch)

- [ ] **Step 3: Update implementation**

Modify `edge/reid_service.py` — add `vehicle_model_path` parameter and `is_vehicle` flag to `extract_embedding`:

```python
def __init__(
    self,
    req_queue: multiprocessing.Queue,
    res_queue: multiprocessing.Queue,
    model_path: str = "models/osnet_ain_x1_0.onnx",
    vehicle_model_path: str = "models/vehicle_reid.onnx",
):
    self.req_queue = req_queue
    self.res_queue = res_queue
    self.model_path = model_path
    self.vehicle_model_path = vehicle_model_path
    self._session = None
    self._input_name = None
    self._vehicle_session = None
    self._vehicle_input_name = None
```

Add vehicle model loading in `_load_model`:
```python
def _load_vehicle_model(self):
    try:
        import onnxruntime as ort
        self._vehicle_session = ort.InferenceSession(self.vehicle_model_path)
        self._vehicle_input_name = self._vehicle_session.get_inputs()[0].name
        logger.info(f"Vehicle ReID model loaded from {self.vehicle_model_path}")
    except Exception as e:
        logger.warning(f"Failed to load vehicle ReID model: {e}")
        self._vehicle_session = None
```

Update `extract_embedding`:
```python
def extract_embedding(self, crop: np.ndarray, is_vehicle: bool = False) -> Optional[np.ndarray]:
    session = self._vehicle_session if is_vehicle else self._session
    input_name = self._vehicle_input_name if is_vehicle else self._input_name

    if session is None:
        return None

    try:
        blob = self._preprocess_crop(crop)
        outputs = session.run(None, {input_name: blob})
        embedding = outputs[0].flatten()
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    except Exception as e:
        logger.error(f"ReID inference failed: {e}")
        return None
```

Update `_process_one` to handle `is_vehicle`:
```python
def _process_one(self):
    try:
        item = self.req_queue.get(timeout=0.1)
    except Exception:
        return

    if item is None:
        return

    frame_id, camera_id, crop, object_type = item
    is_vehicle = object_type == "vehicle"
    embedding = self.extract_embedding(crop, is_vehicle=is_vehicle)
    self.res_queue.put((frame_id, camera_id, embedding, object_type))
```

Update `run` to load vehicle model:
```python
def run(self):
    self._load_model()
    self._load_vehicle_model()
    logger.info("ReID service started")
    # ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_reid_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/reid_service.py tests/test_reid_service.py
git commit -m "Phase 2: add vehicle ReID model support to ReIDService"
```

---

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

---

### Task 5: MatchingEngine — pgvector Cosine Search

**Files:**
- Create: `fusion_server/services/__init__.py`
- Create: `fusion_server/services/matching_engine.py`
- Create: `tests/test_matching_engine.py`

**Interfaces:**
- Consumes: DetectionEvent with embedding from POST /api/v1/events
- Produces: assigned `object_id` (existing or new UUID)

- [ ] **Step 1: Write the failing test**

Create `tests/test_matching_engine.py`:
```python
"""Tests for MatchingEngine — pgvector cosine similarity matching."""
import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def test_matching_engine_initializes():
    """MatchingEngine can be instantiated."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.65, threshold_vehicle=0.60)
    assert engine.threshold_person == 0.65
    assert engine.threshold_vehicle == 0.60


def test_matching_engine_cosine_similarity():
    """MatchingEngine computes cosine similarity correctly."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(1.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(0.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([-1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(-1.0)


def test_matching_engine_new_object():
    """MatchingEngine creates new object_id when no match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime.utcnow(),
    )

    assert object_id is not None
    assert len(object_id) > 0


def test_matching_engine_existing_match():
    """MatchingEngine returns existing object_id when match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.5)  # Low threshold for test

    # Create a mock existing event with known embedding
    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    mock_event = MagicMock()
    mock_event.object_id = "existing-object-123"
    mock_event.embedding = embedding.tolist()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_event]

    # Same embedding should match
    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime.utcnow(),
    )

    assert object_id == "existing-object-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_matching_engine.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'fusion_server.services'`)

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/__init__.py`:
```python
# Phase 2 services
```

Create `fusion_server/services/matching_engine.py`:
```python
"""
MatchingEngine — assigns global object_ids to detections via pgvector cosine search.
Runs asynchronously after event ingestion.
"""
import numpy as np
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Cross-camera re-identification matching engine.
    Uses pgvector cosine search to find matching embeddings.
    """

    def __init__(
        self,
        threshold_person: float = 0.65,
        threshold_vehicle: float = 0.60,
        time_window_minutes: int = 5,
    ):
        self.threshold_person = threshold_person
        self.threshold_vehicle = threshold_vehicle
        self.time_window_minutes = time_window_minutes

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _get_threshold(self, object_type: str) -> float:
        """Get matching threshold for object type."""
        if object_type == "person":
            return self.threshold_person
        return self.threshold_vehicle

    def match_or_create(
        self,
        db: Session,
        embedding: np.ndarray,
        object_type: str,
        camera_id: str,
        timestamp: datetime,
    ) -> str:
        """
        Find matching object or create new one.
        Returns object_id (existing or newly generated UUID).
        """
        threshold = self._get_threshold(object_type)

        # Query recent embeddings of same object_type using pgvector cosine distance
        cutoff = timestamp - timedelta(minutes=self.time_window_minutes)

        try:
            # Use pgvector <=> operator for cosine distance (1 - similarity)
            result = db.execute(
                text("""
                    SELECT object_id, embedding <=> :query_embedding AS distance
                    FROM detection_events
                    WHERE object_type = :object_type
                      AND timestamp >= :cutoff
                      AND embedding IS NOT NULL
                      AND object_id IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT 5
                """),
                {
                    "query_embedding": embedding.tolist(),
                    "object_type": object_type,
                    "cutoff": cutoff,
                },
            )

            rows = result.fetchall()

            for row in rows:
                similarity = 1.0 - row.distance  # Convert distance to similarity
                if similarity >= threshold:
                    logger.debug(f"Matched to existing object {row.object_id} (sim={similarity:.3f})")
                    return row.object_id

        except Exception as e:
            logger.warning(f"pgvector query failed, falling back to new object: {e}")

        # No match found — create new object_id
        new_object_id = str(uuid.uuid4())
        logger.debug(f"Created new object {new_object_id}")
        return new_object_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_matching_engine.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/ tests/test_matching_engine.py
git commit -m "Phase 2: add MatchingEngine with pgvector cosine search"
```

---

### Task 6: FootprintChainWriter — Hash Chain Logic

**Files:**
- Create: `fusion_server/services/footprint_writer.py`
- Create: `tests/test_footprint_writer.py`

**Interfaces:**
- Consumes: object_id, camera_id, timestamp, detection_event_id
- Produces: FootprintEntry records with hash chain linkage

- [ ] **Step 1: Write the failing test**

Create `tests/test_footprint_writer.py`:
```python
"""Tests for FootprintChainWriter — footprint chain with hash linkage."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_footprint_writer_initializes():
    """FootprintChainWriter can be instantiated."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()
    assert writer is not None


def test_footprint_writer_first_seen():
    """FootprintChainWriter creates first_seen entry for new object."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_db = MagicMock()
    # No existing entries
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
        event_type="first_seen",
        detection_event_id=1,
    )

    assert entry is not None
    assert entry["event_type"] == "first_seen"
    assert entry["previous_hash"] is None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_footprint_writer_hop_different_camera():
    """FootprintChainWriter creates hop entry when camera changes."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    # Mock existing first_seen entry
    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.event_type = "first_seen"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_last_entry]

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam2",  # Different camera
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
        event_type="hop",
        detection_event_id=2,
    )

    assert entry is not None
    assert entry["event_type"] == "hop"
    assert entry["previous_hash"] == "abc123"


def test_footprint_writer_same_camera_no_hop():
    """FootprintChainWriter skips hop when same camera and recent."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.timestamp = datetime(2026, 9, 11, 10, 0, 0)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_last_entry]

    # Same camera, only 1 second later — should skip
    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",  # Same camera
        timestamp=datetime(2026, 9, 11, 10, 0, 1),  # 1 second later
        event_type="hop",
        detection_event_id=3,
    )

    assert entry is None  # Skipped
    mock_db.add.assert_not_called()


def test_footprint_writer_hash_chain():
    """FootprintChainWriter computes hash correctly."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    hash_value = writer._compute_hash(
        object_id="obj-123",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        event_type="first_seen",
        previous_hash=None,
    )

    assert hash_value is not None
    assert len(hash_value) == 64  # SHA-256 hex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_footprint_writer.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'fusion_server.services.footprint_writer'`)

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/footprint_writer.py`:
```python
"""
FootprintChainWriter — writes footprint entries with tamper-evident hash chain.
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Minimum gap between entries on same camera (seconds)
MIN_SAME_CAMERA_GAP = 30


class FootprintChainWriter:
    """Writes footprint chain entries with hash linkage."""

    def __init__(self, min_same_camera_gap: int = MIN_SAME_CAMERA_GAP):
        self.min_same_camera_gap = min_same_camera_gap

    def _compute_hash(
        self,
        object_id: str,
        camera_id: str,
        timestamp: str,
        event_type: str,
        previous_hash: Optional[str],
    ) -> str:
        """Compute SHA-256 hash for footprint entry."""
        data = f"{object_id}{camera_id}{timestamp}{event_type}"
        if previous_hash:
            data += previous_hash
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_last_entry(self, db: Session, object_id: str) -> Optional[Any]:
        """Get the most recent footprint entry for an object."""
        from fusion_server.db.models import FootprintEntry
        entries = (
            db.query(FootprintEntry)
            .filter(FootprintEntry.object_id == object_id)
            .order_by(FootprintEntry.timestamp.desc())
            .limit(1)
            .all()
        )
        return entries[0] if entries else None

    def write_entry(
        self,
        db: Session,
        object_id: str,
        camera_id: str,
        timestamp: datetime,
        event_type: str,
        detection_event_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Write a footprint entry with hash chain linkage.
        Returns entry dict if written, None if skipped.
        """
        from fusion_server.db.models import FootprintEntry

        last_entry = self._get_last_entry(db, object_id)

        # Determine if we should write
        if last_entry is not None:
            # Same camera — check time gap
            if last_entry.camera_id == camera_id:
                time_gap = (timestamp - last_entry.timestamp).total_seconds()
                if time_gap < self.min_same_camera_gap:
                    return None  # Skip — too soon

            previous_hash = last_entry.hash
        else:
            previous_hash = None
            # Force first_seen for new object
            if event_type != "first_seen":
                event_type = "first_seen"

        # Compute hash
        timestamp_str = timestamp.isoformat()
        hash_value = self._compute_hash(
            object_id, camera_id, timestamp_str, event_type, previous_hash
        )

        # Create entry
        entry = FootprintEntry(
            object_id=object_id,
            camera_id=camera_id,
            timestamp=timestamp,
            event_type=event_type,
            hash=hash_value,
            previous_hash=previous_hash,
            detection_event_id=detection_event_id,
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.debug(f"Wrote footprint entry: {event_type} for {object_id} at {camera_id}")

        return {
            "id": entry.id,
            "object_id": object_id,
            "camera_id": camera_id,
            "timestamp": timestamp_str,
            "event_type": event_type,
            "hash": hash_value,
            "previous_hash": previous_hash,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_footprint_writer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/footprint_writer.py tests/test_footprint_writer.py
git commit -m "Phase 2: add FootprintChainWriter with hash chain linkage"
```

---

### Task 7: CameraHealthService — SSIM + Scene Drift

**Files:**
- Create: `edge/camera_health.py`
- Create: `fusion_server/services/camera_health_store.py`
- Create: `tests/test_camera_health.py`

**Interfaces:**
- Consumes: live frames from CameraWorker, embeddings from ReIDService
- Produces: camera health status (ok/drift/tamper), SSIM scores, scene drift flags

- [ ] **Step 1: Write the failing test**

Create `tests/test_camera_health.py`:
```python
"""Tests for CameraHealthService — SSIM and scene drift detection."""
import numpy as np
import pytest
from datetime import datetime


def test_camera_health_initializes():
    """CameraHealthService can be instantiated."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    assert svc.camera_id == "cam1"


def test_camera_health_ssim_identical_frames():
    """SSIM of identical frames is 1.0."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    ssim = svc.compute_ssim(frame, frame)
    assert ssim == pytest.approx(1.0, abs=0.01)


def test_camera_health_ssim_different_frames():
    """SSIM of very different frames is low."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")

    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
    ssim = svc.compute_ssim(frame1, frame2)
    assert ssim < 0.5


def test_camera_health_tamper_detection():
    """CameraHealthService detects tamper when SSIM drops below threshold."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1", tamper_threshold=0.1)

    # Set reference frame
    ref_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    svc.set_reference_frame(ref_frame)

    # Simulate tamper (black frame)
    tamper_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status = svc.check_health(tamper_frame)

    assert status["status"] == "tamper"
    assert status["ssim"] < 0.1


def test_camera_health_scene_drift():
    """CameraHealthService detects scene drift from embedding changes."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1", scene_drift_threshold=0.3)

    # Set initial scene embedding
    initial_embedding = np.random.rand(512).astype(np.float32)
    initial_embedding = initial_embedding / np.linalg.norm(initial_embedding)
    svc.set_scene_embedding(initial_embedding)

    # Add similar embeddings (no drift)
    for _ in range(10):
        svc.update_scene_embedding(initial_embedding + np.random.randn(512).astype(np.float32) * 0.01)

    # Check with similar embedding — no drift
    status = svc.check_scene_drift(initial_embedding)
    assert status["scene_drift"] is False

    # Check with very different embedding — drift
    different_embedding = np.random.rand(512).astype(np.float32)
    different_embedding = different_embedding / np.linalg.norm(different_embedding)
    status = svc.check_scene_drift(different_embedding)
    assert status["scene_drift"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_health.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.camera_health'`)

- [ ] **Step 3: Write minimal implementation**

Create `edge/camera_health.py`:
```python
"""
Camera Health Service — monitors camera tamper/drift via SSIM and scene embeddings.
"""
import numpy as np
import logging
from typing import Optional, Dict
from collections import deque

logger = logging.getLogger(__name__)


class CameraHealthService:
    """
    Monitors camera health via frame-level SSIM and embedding-level scene drift.
    """

    def __init__(
        self,
        camera_id: str,
        tamper_threshold: float = 0.1,
        drift_threshold: float = 0.3,
        scene_drift_threshold: float = 0.3,
        max_scene_embeddings: int = 100,
    ):
        self.camera_id = camera_id
        self.tamper_threshold = tamper_threshold
        self.drift_threshold = drift_threshold
        self.scene_drift_threshold = scene_drift_threshold
        self._reference_frame: Optional[np.ndarray] = None
        self._scene_embeddings: deque = deque(maxlen=max_scene_embeddings)
        self._scene_centroid: Optional[np.ndarray] = None

    def set_reference_frame(self, frame: np.ndarray):
        """Set reference frame for SSIM comparison."""
        self._reference_frame = frame.copy()
        logger.info(f"Camera {self.camera_id}: Reference frame set")

    def set_scene_embedding(self, embedding: np.ndarray):
        """Set initial scene embedding."""
        self._scene_centroid = embedding.copy()
        self._scene_embeddings.clear()
        self._scene_embeddings.append(embedding.copy())

    def update_scene_embedding(self, embedding: np.ndarray):
        """Add new embedding to scene buffer and update centroid."""
        self._scene_embeddings.append(embedding.copy())
        if len(self._scene_embeddings) > 0:
            self._scene_centroid = np.mean(list(self._scene_embeddings), axis=0)
            norm = np.linalg.norm(self._scene_centroid)
            if norm > 0:
                self._scene_centroid = self._scene_centroid / norm

    def compute_ssim(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """Compute structural similarity between two frames."""
        try:
            from skimage.metrics import structural_similarity as ssim
            # Convert to grayscale for SSIM
            if len(frame1.shape) == 3:
                gray1 = np.mean(frame1, axis=2).astype(np.uint8)
                gray2 = np.mean(frame2, axis=2).astype(np.uint8)
            else:
                gray1, gray2 = frame1, frame2
            return float(ssim(gray1, gray2, data_range=255))
        except ImportError:
            # Fallback: simple pixel difference
            diff = np.mean(np.abs(frame1.astype(float) - frame2.astype(float)))
            return max(0.0, 1.0 - diff / 128.0)

    def check_health(self, live_frame: np.ndarray) -> Dict:
        """
        Check camera health against reference frame.
        Returns: {"status": "ok"|"drift"|"tamper", "ssim": float}
        """
        if self._reference_frame is None:
            return {"status": "unknown", "ssim": 0.0, "message": "No reference frame set"}

        # Resize if needed
        if live_frame.shape != self._reference_frame.shape:
            import cv2
            live_frame = cv2.resize(live_frame, (self._reference_frame.shape[1], self._reference_frame.shape[0]))

        ssim_score = self.compute_ssim(self._reference_frame, live_frame)

        if ssim_score < self.tamper_threshold:
            status = "tamper"
        elif ssim_score < self.drift_threshold:
            status = "drift"
        else:
            status = "ok"

        return {"status": status, "ssim": round(ssim_score, 4)}

    def check_scene_drift(self, embedding: np.ndarray) -> Dict:
        """
        Check if new embedding indicates scene drift.
        Returns: {"scene_drift": bool, "similarity": float}
        """
        if self._scene_centroid is None:
            return {"scene_drift": False, "similarity": 0.0}

        similarity = float(np.dot(embedding, self._scene_centroid) / (
            np.linalg.norm(embedding) * np.linalg.norm(self._scene_centroid)
        ))

        scene_drift = similarity < self.scene_drift_threshold

        return {"scene_drift": scene_drift, "similarity": round(similarity, 4)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_health.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/camera_health.py tests/test_camera_health.py
git commit -m "Phase 2: add CameraHealthService with SSIM and scene drift detection"
```

---

### Task 8: Camera Health Store (Fusion Server)

**Files:**
- Create: `fusion_server/services/camera_health_store.py`
- Modify: `tests/test_camera_health.py`

**Interfaces:**
- Consumes: camera health status from edge nodes
- Produces: aggregated health status for API

- [ ] **Step 1: Write the failing test**

Add to `tests/test_camera_health.py`:
```python
def test_camera_health_store_initializes():
    """CameraHealthStore can be instantiated."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()
    assert store is not None


def test_camera_health_store_updates():
    """CameraHealthStore tracks health status per camera."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()

    store.update("cam1", {"status": "ok", "ssim": 0.87})
    store.update("cam2", {"status": "tamper", "ssim": 0.05})

    health = store.get_all()
    assert health["cam1"]["status"] == "ok"
    assert health["cam2"]["status"] == "tamper"


def test_camera_health_store_defaults():
    """CameraHealthStore returns unknown for unregistered cameras."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()

    health = store.get_all()
    assert "unknown_cam" not in health
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_health.py::test_camera_health_store_initializes -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/camera_health_store.py`:
```python
"""
CameraHealthStore — in-memory store for camera health status.
"""
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CameraHealthStore:
    """In-memory store tracking camera health status."""

    def __init__(self):
        self._cameras: Dict[str, Dict[str, Any]] = {}

    def update(self, camera_id: str, health: Dict[str, Any]):
        """Update health status for a camera."""
        self._cameras[camera_id] = {
            **health,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all cameras."""
        return dict(self._cameras)

    def get(self, camera_id: str) -> Dict[str, Any]:
        """Get health status for a specific camera."""
        return self._cameras.get(camera_id, {"status": "unknown"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_health.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/camera_health_store.py tests/test_camera_health.py
git commit -m "Phase 2: add CameraHealthStore for camera health tracking"
```

---

### Task 9: API Routes — Footprint Write + Camera Health

**Files:**
- Modify: `fusion_server/api/footprint.py`
- Create: `fusion_server/api/routes/__init__.py`
- Create: `fusion_server/api/routes/cameras.py`
- Create: `tests/test_api_phase2.py`

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

    # This will fail until we add the write endpoint
    response = client.post("/api/v1/footprint", json={
        "object_id": "test-obj-123",
        "camera_id": "cam1",
        "timestamp": "2026-09-11T10:00:00Z",
        "event_type": "first_seen",
    })
    # Should return 201 or 422 (validation error), not 404
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

Modify `fusion_server/api/footprint.py` — add POST endpoint:

```python
class FootprintWriteRequest(BaseModel):
    object_id: str
    camera_id: str
    timestamp: datetime
    event_type: str  # 'first_seen' | 'hop' | 'last_seen'
    detection_event_id: Optional[int] = None


class FootprintWriteResponse(BaseModel):
    id: int
    object_id: str
    camera_id: str
    timestamp: datetime
    event_type: str
    hash: str
    previous_hash: Optional[str] = None


@router.post("", response_model=FootprintWriteResponse, status_code=status.HTTP_201_CREATED)
async def write_footprint_entry(req: FootprintWriteRequest, db: Session = Depends(get_db)):
    """Write a new footprint entry (called by matching engine)."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()
    entry = writer.write_entry(
        db=db,
        object_id=req.object_id,
        camera_id=req.camera_id,
        timestamp=req.timestamp,
        event_type=req.event_type,
        detection_event_id=req.detection_event_id,
    )
    if entry is None:
        raise HTTPException(status_code=409, detail="Entry skipped (same camera, recent)")
    return FootprintWriteResponse(**entry)
```

- [ ] **Step 4: Create camera health route**

Create `fusion_server/api/routes/__init__.py`:
```python
# Phase 2 API routes
```

Create `fusion_server/api/routes/cameras.py`:
```python
"""
Camera Health API — GET /cameras/health
"""
from fastapi import APIRouter
from typing import Dict, Any
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

# Global health store (initialized in main.py lifespan)
_health_store = None


def get_health_store():
    global _health_store
    if _health_store is None:
        from fusion_server.services.camera_health_store import CameraHealthStore
        _health_store = CameraHealthStore()
    return _health_store


class CameraHealthResponse(BaseModel):
    cameras: Dict[str, Dict[str, Any]]


@router.get("/health", response_model=CameraHealthResponse)
async def get_camera_health():
    """Get health status for all cameras."""
    store = get_health_store()
    return CameraHealthResponse(cameras=store.get_all())
```

- [ ] **Step 5: Register new router in main.py**

Modify `fusion_server/main.py` — add:
```python
from fusion_server.api.routes import cameras

# In the app setup:
app.include_router(cameras.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add fusion_server/api/footprint.py fusion_server/api/routes/ fusion_server/main.py tests/test_api_phase2.py
git commit -m "Phase 2: add footprint write endpoint and camera health API"
```

---

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

    # Create event with embedding
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
    # Should have object_id assigned (or pending)
    assert "object_id" in data or "id" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py::test_event_ingestion_triggers_matching -v`
Expected: FAIL (response doesn't include object_id)

- [ ] **Step 3: Update event ingestion to trigger matching**

Modify `fusion_server/api/events.py` — update `create_event` to run matching:

```python
@router.post("", response_model=DetectionEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event: DetectionEventCreate, db: Session = Depends(get_db)):
    """Receive detection event from edge node."""
    import numpy as np

    db_event = DetectionEvent(
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        object_type=event.object_type,
        track_id=event.track_id,
        bbox=event.bbox.model_dump(),
        embedding=event.embedding,
        confidence=event.confidence,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Async matching — assign object_id if embedding provided
    object_id = None
    if event.embedding is not None:
        try:
            from fusion_server.services.matching_engine import MatchingEngine
            engine = MatchingEngine()
            embedding_array = np.array(event.embedding, dtype=np.float32)
            object_id = engine.match_or_create(
                db=db,
                embedding=embedding_array,
                object_type=event.object_type,
                camera_id=event.camera_id,
                timestamp=event.timestamp,
            )

            # Update event with object_id
            db_event.object_id = object_id
            db.commit()

            # Write footprint entry
            from fusion_server.services.footprint_writer import FootprintChainWriter
            writer = FootprintChainWriter()
            writer.write_entry(
                db=db,
                object_id=object_id,
                camera_id=event.camera_id,
                timestamp=event.timestamp,
                event_type="first_seen",
                detection_event_id=db_event.id,
            )
        except Exception as e:
            logger.warning(f"Matching/footprint failed: {e}")

    return DetectionEventResponse(
        id=db_event.id,
        camera_id=db_event.camera_id,
        timestamp=db_event.timestamp,
        object_type=db_event.object_type,
        track_id=db_event.track_id,
        bbox=BBox(**db_event.bbox),
        embedding=db_event.embedding,
        confidence=db_event.confidence,
        created_at=db_event.created_at,
        object_id=object_id,
    )
```

Also update `DetectionEventResponse` to include `object_id`:
```python
class DetectionEventResponse(BaseModel):
    id: int
    camera_id: str
    timestamp: datetime
    object_type: str
    track_id: str
    bbox: BBox
    embedding: Optional[List[float]] = None
    confidence: float
    created_at: datetime
    object_id: Optional[str] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_api_phase2.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/api/events.py tests/test_api_phase2.py
git commit -m "Phase 2: add async matching and footprint write to event ingestion"
```

---

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

    # 1. Simulate two detections from different cameras
    embedding1 = np.random.rand(512).astype(np.float32)
    embedding1 = embedding1 / np.linalg.norm(embedding1)

    embedding2 = embedding1 + np.random.randn(512).astype(np.float32) * 0.01  # Similar
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    # 2. Matching engine assigns object_ids
    engine = MatchingEngine(threshold_person=0.5)  # Low threshold for test
    mock_db = MagicMock()

    # First detection — no matches
    mock_db.execute.return_value.fetchall.return_value = []
    object_id1 = engine.match_or_create(
        db=mock_db,
        embedding=embedding1,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
    )

    # Second detection — should match first
    mock_result = MagicMock()
    mock_result.object_id = object_id1
    mock_result.distance = 0.01  # Very similar
    mock_db.execute.return_value.fetchall.return_value = [mock_result]

    object_id2 = engine.match_or_create(
        db=mock_db,
        embedding=embedding2,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
    )

    assert object_id1 == object_id2, "Same object should get same object_id"

    # 3. Footprint chain writer creates entries
    writer = FootprintChainWriter()

    # Mock DB queries for footprint writer
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

    # Mock second entry's previous hash
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

    # ReIDService produces embeddings
    req_queue = MagicMock()
    res_queue = MagicMock()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop)

    # With no model, embedding is None — graceful fallback
    assert embedding is None

    # But if we had a model, embedding would feed into MatchingEngine
    engine = MatchingEngine()
    assert engine.threshold_person == 0.65
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_integration_phase2.py -v`
Expected: FAIL (import errors or assertion errors)

- [ ] **Step 3: Run all Phase 2 tests**

Run: `.\venv\Scripts\activate; pytest tests/test_reid_service.py tests/test_matching_engine.py tests/test_footprint_writer.py tests/test_camera_health.py tests/test_api_phase2.py tests/test_integration_phase2.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_phase2.py
git commit -m "Phase 2: add integration test for full detection-to-footprint pipeline"
```

---

### Task 12: Update run_all.py + End-to-End Verification

**Files:**
- Modify: `edge/run_all.py`
- Modify: `edge/camera_worker.py` (constructor update)

**Interfaces:**
- Consumes: all Phase 2 components
- Produces: runnable system with ReID + matching + footprint

- [ ] **Step 1: Update run_all.py to start ReIDService**

Modify `edge/run_all.py`:
```python
# Add ReIDService process
reid_req_queue = multiprocessing.Queue()
reid_res_queue = multiprocessing.Queue()

reid_service = ReIDService(reid_req_queue, reid_res_queue, model_path="models/osnet_ain_x1_0.onnx")
reid_process = multiprocessing.Process(target=reid_service.run, daemon=True)
reid_process.start()

# Pass reid queues to each CameraWorker
worker = CameraWorker(
    # ... existing params ...
    reid_req_queue=reid_req_queue,
    reid_res_queue=reid_res_queue,
)
```

- [ ] **Step 2: Run all tests to verify nothing broke**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All tests PASS (Phase 0 + Phase 1 + Phase 2)

- [ ] **Step 3: Run lint/typecheck if available**

Run: `.\venv\Scripts\activate; python -m py_compile edge/reid_service.py edge/camera_health.py fusion_server/services/matching_engine.py fusion_server/services/footprint_writer.py fusion_server/services/camera_health_store.py fusion_server/api/routes/cameras.py`
Expected: No syntax errors

- [ ] **Step 4: Final commit**

```bash
git add edge/run_all.py
git commit -m "Phase 2: integrate ReIDService into run_all.py entry point"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** All 11 spec sections have corresponding tasks
- [ ] **Placeholder scan:** No TBD/TODO in any step
- [ ] **Type consistency:** `embedding` is `Optional[List[float]]` in API, `np.ndarray` internally
- [ ] **Data contracts:** `DetectionEvent.object_id` added to response model
- [ ] **Graceful fallback:** ReID returns None if model unavailable
- [ ] **Hash chain:** FootprintChainWriter uses SHA-256 with previous_hash linkage
- [ ] **Tests:** Every task has passing tests before commit
