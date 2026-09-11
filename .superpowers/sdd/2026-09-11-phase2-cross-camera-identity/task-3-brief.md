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
