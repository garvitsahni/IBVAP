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
    ref_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    svc.set_reference_frame(ref_frame)
    tamper_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status = svc.check_health(tamper_frame)
    assert status["status"] == "tamper"
    assert status["ssim"] < 0.1


def test_camera_health_scene_drift():
    """CameraHealthService detects scene drift from embedding changes."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1", scene_drift_threshold=0.3)
    initial_embedding = np.random.rand(512).astype(np.float32)
    initial_embedding = initial_embedding / np.linalg.norm(initial_embedding)
    svc.set_scene_embedding(initial_embedding)
    for _ in range(10):
        svc.update_scene_embedding(initial_embedding + np.random.randn(512).astype(np.float32) * 0.01)
    status = svc.check_scene_drift(initial_embedding)
    assert status["scene_drift"] is False
    different_embedding = np.random.rand(512).astype(np.float32)
    different_embedding = different_embedding / np.linalg.norm(different_embedding)
    status = svc.check_scene_drift(different_embedding)
    assert status["scene_drift"] is True


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
        self._reference_frame = frame.copy()

    def set_scene_embedding(self, embedding: np.ndarray):
        self._scene_centroid = embedding.copy()
        self._scene_embeddings.clear()
        self._scene_embeddings.append(embedding.copy())

    def update_scene_embedding(self, embedding: np.ndarray):
        self._scene_embeddings.append(embedding.copy())
        if len(self._scene_embeddings) > 0:
            self._scene_centroid = np.mean(list(self._scene_embeddings), axis=0)
            norm = np.linalg.norm(self._scene_centroid)
            if norm > 0:
                self._scene_centroid = self._scene_centroid / norm

    def compute_ssim(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        try:
            from skimage.metrics import structural_similarity as ssim
            if len(frame1.shape) == 3:
                gray1 = np.mean(frame1, axis=2).astype(np.uint8)
                gray2 = np.mean(frame2, axis=2).astype(np.uint8)
            else:
                gray1, gray2 = frame1, frame2
            return float(ssim(gray1, gray2, data_range=255))
        except ImportError:
            diff = np.mean(np.abs(frame1.astype(float) - frame2.astype(float)))
            return max(0.0, 1.0 - diff / 128.0)

    def check_health(self, live_frame: np.ndarray) -> Dict:
        if self._reference_frame is None:
            return {"status": "unknown", "ssim": 0.0, "message": "No reference frame set"}
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
        if self._scene_centroid is None:
            return {"scene_drift": False, "similarity": 0.0}
        similarity = float(np.dot(embedding, self._scene_centroid) / (
            np.linalg.norm(embedding) * np.linalg.norm(self._scene_centroid)
        ))
        scene_drift = similarity < self.scene_drift_threshold
        return {"scene_drift": scene_drift, "similarity": round(similarity, 4)}
```

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
    def __init__(self):
        self._cameras: Dict[str, Dict[str, Any]] = {}

    def update(self, camera_id: str, health: Dict[str, Any]):
        self._cameras[camera_id] = {
            **health,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._cameras)

    def get(self, camera_id: str) -> Dict[str, Any]:
        return self._cameras.get(camera_id, {"status": "unknown"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_camera_health.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/camera_health.py fusion_server/services/camera_health_store.py tests/test_camera_health.py
git commit -m "Phase 2: add CameraHealthService with SSIM, scene drift, and health store"
```
