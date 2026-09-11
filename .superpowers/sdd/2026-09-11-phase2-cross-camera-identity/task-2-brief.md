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
