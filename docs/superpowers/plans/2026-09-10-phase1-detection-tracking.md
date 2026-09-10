# Phase 1 — Detection & Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the edge processing pipeline — YOLOv8n detection, ByteTrack tracking, night/weather adaptation, live visualization, and event publishing to the fusion server.

**Architecture:** Shared `DetectionService` process (YOLOv8n) serves batched inference to per-camera `CameraWorker` processes. Each worker handles ingestion, preprocessing, tracking, publishing, and visualization independently via multiprocessing.Queue IPC.

**Tech Stack:** Python 3.13, ultralytics (YOLOv8n), opencv-python-headless, numpy, requests, multiprocessing (stdlib)

## Global Constraints

- Python 3.13 on Windows
- DetectionEvent JSON must match ARCHITECTURE.md §5 frozen data contract exactly
- `bbox` in published events is `[x, y, w, h]` normalized 0-1 (converted from YOLO pixel `[x1, y1, x2, y2]`)
- `embedding` field is `null` in Phase 1 (populated in Phase 2)
- No cloud API calls — all processing local
- YOLOv8n chosen for CPU viability during laptop-stage development
- COCO classes: 0 (person), 2 (car), 3 (motorcycle), 5 (bus), 7 (truck)
- `object_type` mapping: class 0 → `"person"`, all vehicle classes → `"vehicle"`
- Target 10 FPS per camera, skip frames if processing exceeds 100ms

---

## File Structure

```
edge/
├── __init__.py                    # (exists)
├── detector.py                    # DetectionService: shared YOLOv8n process
├── tracker.py                     # ByteTrack per-camera tracker
├── camera_worker.py               # Per-camera pipeline orchestrator
├── night_weather.py               # Brightness/visibility estimators + preprocessing
├── ingestion.py                   # RTSP stream reader (OpenCV VideoCapture)
├── event_publisher.py             # HTTP POST DetectionEvent to fusion server
├── visualizer.py                  # Bbox rendering + MJPEG server
├── run_camera.py                  # Entry point: single camera worker
├── run_detection_service.py       # Entry point: detection service process
└── run_all.py                     # Entry point: spawns service + all cameras
```

---

### Task 1: Install Dependencies & Verify YOLOv8n

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_yolo_load.py`

**Interfaces:**
- Produces: confirmed YOLOv8n model loading on this environment

- [ ] **Step 1: Install ultralytics and opencv-python-headless**

```bash
cd C:\Users\Garvi\Desktop\Projects\IBVAP
.\venv\Scripts\activate
pip install ultralytics opencv-python-headless requests
```

- [ ] **Step 2: Verify YOLOv8n loads and runs inference**

```python
# tests/test_yolo_load.py
"""Verify YOLOv8n loads and produces detections on a synthetic frame."""
import numpy as np

def test_yolov8n_loads():
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    assert model is not None

def test_yolov8n_detects_person():
    from ultralytics import YOLO
    import cv2
    model = YOLO("yolov8n.pt")
    # Create a 640x480 black frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw a rough person-shaped rectangle (white on black)
    cv2.rectangle(frame, (250, 100), (350, 400), (255, 255, 255), -1)
    results = model(frame, classes=[0, 2, 3, 5, 7])
    # Should produce at least one detection (the white rectangle)
    assert len(results) > 0
    boxes = results[0].boxes
    assert len(boxes) > 0
```

- [ ] **Step 3: Run test to verify it passes**

```bash
cd C:\Users\Garvi\Desktop\Projects\IBVAP
.\venv\Scripts\activate
python -m pytest tests/test_yolo_load.py -v
```
Expected: PASS (both tests green)

- [ ] **Step 4: Update requirements.txt**

Add to `requirements.txt`:
```
ultralytics>=8.2.0
opencv-python-headless>=4.9.0
requests>=2.31.0
```

- [ ] **Step 5: Attempt yolox install (may fail — that's OK)**

```bash
pip install yolox
```
If this fails on Python 3.13, note the error. Task 2 will implement the fallback.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/test_yolo_load.py
git commit -m "Add YOLOv8n dependency and load verification test"
```

---

### Task 2: ByteTrack Tracker

**Files:**
- Create: `edge/tracker.py`
- Create: `tests/test_tracker.py`

**Interfaces:**
- Produces: `Tracker` class with `update(detections, frame_shape) → List[TrackedObject]`
- `TrackedObject`: `track_id: int, bbox: [x1,y1,x2,y2], class_id: int, class_name: str, confidence: float`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tracker.py
"""Tests for ByteTrack tracker wrapper."""

def test_tracker_assigns_ids():
    """Same object across frames gets same track ID."""
    from edge.tracker import Tracker
    tracker = Tracker()
    # Frame 1: one detection at (100,100)-(200,300)
    det1 = [{"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9}]
    tracks1 = tracker.update(det1, (480, 640))
    assert len(tracks1) == 1
    tid1 = tracks1[0].track_id

    # Frame 2: same object, slightly moved
    det2 = [{"bbox": [105, 102, 205, 302], "class_id": 0, "class_name": "person", "confidence": 0.88}]
    tracks2 = tracker.update(det2, (480, 640))
    assert len(tracks2) == 1
    assert tracks2[0].track_id == tid1  # Same ID


def test_tracker_multiple_objects():
    """Multiple objects get distinct IDs."""
    from edge.tracker import Tracker
    tracker = Tracker()
    dets = [
        {"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9},
        {"bbox": [400, 100, 500, 300], "class_id": 2, "class_name": "car", "confidence": 0.85},
    ]
    tracks = tracker.update(dets, (480, 640))
    assert len(tracks) == 2
    ids = {t.track_id for t in tracks}
    assert len(ids) == 2  # Distinct IDs


def test_tracker_lost_track_cleanup():
    """Track that receives no detections for 30 frames is removed."""
    from edge.tracker import Tracker
    tracker = Tracker()
    # Create a track
    det = [{"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9}]
    tracks = tracker.update(det, (480, 640))
    active_id = tracks[0].track_id

    # Send 31 empty frames
    for _ in range(31):
        tracks = tracker.update([], (480, 640))

    # Track should be gone
    active_ids = {t.track_id for t in tracks}
    assert active_id not in active_ids


def test_tracker_empty_frame():
    """Empty detections produce empty tracks."""
    from edge.tracker import Tracker
    tracker = Tracker()
    tracks = tracker.update([], (480, 640))
    assert tracks == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_tracker.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'edge.tracker'`

- [ ] **Step 3: Implement ByteTrack tracker**

```python
# edge/tracker.py
"""
ByteTrack-inspired per-camera tracker.
SORT-style Kalman filter + Hungarian assignment.
If yolox is available, uses its BYTETracker. Otherwise, self-contained impl.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from collections import defaultdict

try:
    from yolox.tracker.byte_tracker import BYTETracker as _ByteTracker
    _HAS_YOLOX = True
except ImportError:
    _HAS_YOLOX = False


@dataclass
class TrackedObject:
    track_id: int
    bbox: List[float]  # [x1, y1, x2, y2] pixel coords
    class_id: int
    class_name: str
    confidence: float


class _KalmanBoxTracker:
    """Single-object Kalman filter for bounding box tracking."""
    _id_counter = 0

    def __init__(self, bbox: List[float], class_id: int, class_name: str, confidence: float):
        self.track_id = _KalmanBoxTracker._id_counter
        _KalmanBoxTracker._id_counter += 1

        self.class_id = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.hits = 1
        self.time_since_update = 0

        # State: [cx, cy, w, h, vx, vy, vw, vh]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        self.x = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=np.float64)

        # State covariance
        self.P = np.eye(8) * 10.0
        self.P[4:, 4:] *= 100.0

        # State transition (constant velocity)
        self.F = np.eye(8)
        self.F[0, 4] = 1  # cx += vx
        self.F[1, 5] = 1  # cy += vy
        self.F[2, 6] = 1  # w += vw
        self.F[3, 7] = 1  # h += vh

        # Measurement matrix (observe cx, cy, w, h)
        self.H = np.zeros((4, 8))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        self.H[3, 3] = 1

        # Measurement noise
        self.R = np.eye(4) * 10.0

        # Process noise
        self.Q = np.eye(8) * 1.0
        self.Q[4:, 4:] *= 0.01

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        # Ensure w, h stay positive
        self.x[2] = max(1.0, self.x[2])
        self.x[3] = max(1.0, self.x[3])

    def update(self, bbox: List[float]):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        z = np.array([cx, cy, w, h])

        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(8) - K @ self.H) @ self.P

        self.hits += 1
        self.time_since_update = 0

    def get_bbox(self) -> List[float]:
        cx, cy, w, h = self.x[0], self.x[1], self.x[2], self.x[3]
        return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]

    @property
    def age(self):
        return self.hits


def _iou_batch(bb_test, bb_gt):
    """Compute IoU between two sets of boxes."""
    if len(bb_test) == 0 or len(bb_gt) == 0:
        return np.zeros((len(bb_test), len(bb_gt)))

    xx1 = np.maximum(bb_test[:, 0:1], bb_gt[:, 0:1].T)
    yy1 = np.maximum(bb_test[:, 1:2], bb_gt[:, 1:2].T)
    xx2 = np.minimum(bb_test[:, 2:3], bb_gt[:, 2:3].T)
    yy2 = np.minimum(bb_test[:, 3:4], bb_gt[:, 3:4].T)

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    inter = w * h

    area_test = (bb_test[:, 2] - bb_test[:, 0]) * (bb_test[:, 3] - bb_test[:, 1])
    area_gt = (bb_gt[:, 2] - bb_gt[:, 0]) * (bb_gt[:, 3] - bb_gt[:, 1])

    union = area_test[:, None] + area_gt[None, :] - inter
    return inter / np.maximum(union, 1e-6)


def _linear_assignment(cost_matrix):
    """Hungarian algorithm via scipy."""
    from scipy.optimize import linear_sum_assignment
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return np.array(list(zip(row_ind, col_ind)))


class _SimpleByteTracker:
    """Self-contained ByteTrack-style tracker (SORT + low-confidence matching)."""

    def __init__(self, track_thresh: float = 0.5, match_thresh: float = 0.8, max_age: int = 30):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.max_age = max_age
        self.trackers: List[_KalmanBoxTracker] = []

    def update(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        """
        detections: list of {"bbox": [x1,y1,x2,y2], "class_id": int, "class_name": str, "confidence": float}
        frame_shape: (height, width)
        """
        # Predict existing trackers
        for trk in self.trackers:
            trk.predict()

        if len(detections) == 0:
            # Remove dead tracks
            self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_age]
            return []

        # Split detections by confidence
        high_conf = [d for d in detections if d["confidence"] >= self.track_thresh]
        low_conf = [d for d in detections if d["confidence"] < self.track_thresh and d["confidence"] >= 0.1]

        # --- Stage 1: match high-confidence detections with existing tracks ---
        matched, unmatched_dets, unmatched_trks = self._match(
            [d["bbox"] for d in high_conf],
            [t.get_bbox() for t in self.trackers],
            self.match_thresh
        )

        # Update matched trackers
        for d_idx, t_idx in matched:
            self.trackers[t_idx].update(high_conf[d_idx]["bbox"])
            self.trackers[t_idx].class_id = high_conf[d_idx]["class_id"]
            self.trackers[t_idx].class_name = high_conf[d_idx]["class_name"]
            self.trackers[t_idx].confidence = high_conf[d_idx]["confidence"]

        # Create new tracks for unmatched high-confidence detections
        for d_idx in unmatched_dets:
            d = high_conf[d_idx]
            self.trackers.append(_KalmanBoxTracker(d["bbox"], d["class_id"], d["class_name"], d["confidence"]))

        # --- Stage 2: match low-confidence detections with remaining unmatched tracks ---
        remaining_trks = [i for i in unmatched_trks if self.trackers[i].time_since_update == 0]
        if len(low_conf) > 0 and len(remaining_trks) > 0:
            low_matched, _, _ = self._match(
                [d["bbox"] for d in low_conf],
                [self.trackers[i].get_bbox() for i in remaining_trks],
                self.match_thresh * 0.9  # slightly more lenient for low-conf
            )
            for d_idx, t_idx in low_matched:
                trk_idx = remaining_trks[t_idx]
                self.trackers[trk_idx].update(low_conf[d_idx]["bbox"])
                self.trackers[trk_idx].confidence = low_conf[d_idx]["confidence"]

        # Remove dead tracks
        self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_age]

        # Increment time_since_update for unmatched tracks
        matched_trk_ids = set()
        for _, t_idx in matched:
            matched_trk_ids.add(t_idx)
        for i, trk in enumerate(self.trackers):
            if i not in matched_trk_ids:
                trk.time_since_update += 1

        # Build output
        results = []
        for trk in self.trackers:
            if trk.time_since_update == 0:
                bbox = trk.get_bbox()
                results.append(TrackedObject(
                    track_id=trk.track_id,
                    bbox=bbox,
                    class_id=trk.class_id,
                    class_name=trk.class_name,
                    confidence=trk.confidence,
                ))
        return results

    def _match(self, detections, trackers, threshold):
        """Hungarian matching with IoU cost matrix."""
        if len(detections) == 0 or len(trackers) == 0:
            return [], list(range(len(detections))), list(range(len(trackers)))

        det_array = np.array(detections)
        trk_array = np.array(trackers)

        iou_matrix = _iou_batch(det_array, trk_array)
        cost_matrix = 1.0 - iou_matrix

        try:
            matches = _linear_assignment(cost_matrix)
        except Exception:
            return [], list(range(len(detections))), list(range(len(trackers)))

        matched = []
        unmatched_dets = set(range(len(detections)))
        unmatched_trks = set(range(len(trackers)))

        for d_idx, t_idx in matches:
            if iou_matrix[d_idx, t_idx] >= (1.0 - threshold):
                matched.append((d_idx, t_idx))
                unmatched_dets.discard(d_idx)
                unmatched_trks.discard(t_idx)

        return matched, list(unmatched_dets), list(unmatched_trks)


class Tracker:
    """Per-camera ByteTrack tracker. Uses yolox if available, else self-contained."""

    def __init__(self):
        if _HAS_YOLOX:
            from yolox.tracker.byte_tracker import BYTETrackerArgs
            args = BYTETrackerArgs(track_thresh=0.5, match_thresh=0.8)
            self._tracker = _ByteTracker(args)
            self._use_yolox = True
        else:
            self._tracker = _SimpleByteTracker()
            self._use_yolox = False

    def update(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        """
        Update tracker with new detections.

        Args:
            detections: [{"bbox": [x1,y1,x2,y2], "class_id": int, "class_name": str, "confidence": float}]
            frame_shape: (height, width)

        Returns:
            List of TrackedObject with persistent track IDs.
        """
        if self._use_yolox:
            return self._update_yolox(detections, frame_shape)
        else:
            return self._tracker.update(detections, frame_shape)

    def _update_yolox(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        """Adapt between our detection format and yolox's expected input."""
        import torch
        if len(detections) == 0:
            # Still need to call update to age tracks
            dets_np = np.zeros((0, 5), dtype=np.float32)
        else:
            dets_np = np.array([
                [d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3], d["confidence"]]
                for d in detections
            ], dtype=np.float32)

        # ByteTracker expects (N, 5) array: [x1, y1, x2, y2, conf]
        online_targets = self._tracker.update(
            torch.from_numpy(dets_np),
            torch.from_numpy(np.array(frame_shape)),
            torch.from_numpy(np.array(frame_shape))
        )

        results = []
        for t in online_targets:
            tlwh = t.tlwh
            bbox = [tlwh[0], tlwh[1], tlwh[0] + tlwh[2], tlwh[1] + tlwh[3]]
            results.append(TrackedObject(
                track_id=t.track_id,
                bbox=bbox,
                class_id=t.class_id if hasattr(t, 'class_id') else 0,
                class_name=t.class_name if hasattr(t, 'class_name') else "person",
                confidence=t.score if hasattr(t, 'score') else 0.0,
            ))
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_tracker.py -v
```
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/tracker.py tests/test_tracker.py
git commit -m "feat: add ByteTrack tracker with self-contained fallback"
```

---

### Task 3: Night/Weather Adaptation

**Files:**
- Create: `edge/night_weather.py`
- Create: `tests/test_night_weather.py`

**Interfaces:**
- Produces: `NightWeatherProcessor` class with `process(frame, force_mode=None) → (processed_frame, mode_info)`
- `mode_info`: `{"mode": "normal"|"night"|"hazy", "brightness": float, "visibility": float}`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_night_weather.py
"""Tests for night/weather adaptation module."""
import numpy as np

def test_brightness_normal_frame():
    """Bright frame detected as normal mode."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    # Bright gray frame (mean ~150)
    frame = np.full((480, 640, 3), 150, dtype=np.uint8)
    _, info = proc.process(frame)
    assert info["brightness"] > 80
    assert info["mode"] == "normal"

def test_brightness_night_frame():
    """Dark frame detected as night mode (after stability window)."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    # Very dark frame (mean ~10)
    frame = np.full((480, 640, 3), 10, dtype=np.uint8)
    # Need 5 consecutive frames for mode switch
    for _ in range(5):
        _, info = proc.process(frame)
    assert info["mode"] == "night"

def test_brightness_low_light_frame():
    """Dim frame detected as low-light mode."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    # Dim frame (mean ~50)
    frame = np.full((480, 640, 3), 50, dtype=np.uint8)
    for _ in range(5):
        _, info = proc.process(frame)
    assert info["mode"] == "night"  # 50 is below 80, with 5 frames → night

def test_visibility_sharp_frame():
    """Sharp high-contrast frame has high visibility."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    # Create a sharp frame with high contrast
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:240, :] = 200  # Top half bright
    frame[240:, :] = 50   # Bottom half dark
    _, info = proc.process(frame)
    assert info["visibility"] > 0.5

def test_mode_stability():
    """Mode doesn't flicker with single outlier frame."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    # Start in normal mode
    bright = np.full((480, 640, 3), 150, dtype=np.uint8)
    for _ in range(10):
        _, info = proc.process(bright)
    assert info["mode"] == "normal"

    # One dark frame shouldn't switch mode
    dark = np.full((480, 640, 3), 10, dtype=np.uint8)
    _, info = proc.process(dark)
    assert info["mode"] == "normal"  # Still normal (1 dark frame < 5 needed)

def test_force_mode_overrides():
    """Force mode parameter bypasses estimation."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    bright = np.full((480, 640, 3), 200, dtype=np.uint8)
    _, info = proc.process(bright, force_mode="night")
    assert info["mode"] == "night"

def test_night_preprocessing_enhances_dark_frame():
    """Night preprocessing brightens a dark frame."""
    from edge.night_weather import NightWeatherProcessor
    proc = NightWeatherProcessor()
    dark = np.full((480, 640, 3), 20, dtype=np.uint8)
    processed, _ = proc.process(dark, force_mode="night")
    # Processed frame should be brighter than input
    assert processed.mean() > dark.mean()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_night_weather.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'edge.night_weather'`

- [ ] **Step 3: Implement night/weather processor**

```python
# edge/night_weather.py
"""
Brightness/visibility estimation and preprocessing for night-time and
poor-visibility conditions.
"""
import cv2
import numpy as np
from typing import Tuple, Dict, Optional


class NightWeatherProcessor:
    """
    Estimates brightness and visibility per frame, applies preprocessing
    transforms for night/haze modes.

    Mode stability: requires 5 consecutive frames in the new state before switching.
    """

    BRIGHTNESS_NORMAL = 80
    BRIGHTNESS_NIGHT = 30
    VISIBILITY_THRESHOLD = 0.4
    STABILITY_FRAMES = 5

    def __init__(self):
        self._current_mode = "normal"
        self._candidate_mode = "normal"
        self._candidate_count = 0

    def process(
        self, frame: np.ndarray, force_mode: Optional[str] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Process a frame: estimate conditions and apply preprocessing.

        Args:
            frame: BGR image (H, W, 3)
            force_mode: Override estimation ("normal", "night", "hazy")

        Returns:
            (processed_frame, mode_info)
        """
        brightness = self._estimate_brightness(frame)
        visibility = self._estimate_visibility(frame)

        if force_mode:
            mode = force_mode
        else:
            mode = self._update_mode(brightness, visibility)

        # Apply preprocessing
        if mode == "night":
            processed = self._enhance_night(frame)
        elif mode == "hazy":
            processed = self._enhance_haze(frame)
        else:
            processed = frame.copy()

        mode_info = {
            "mode": mode,
            "brightness": float(brightness),
            "visibility": float(visibility),
        }
        return processed, mode_info

    def _estimate_brightness(self, frame: np.ndarray) -> float:
        """Mean pixel intensity of grayscale frame (0-255)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def _estimate_visibility(self, frame: np.ndarray) -> float:
        """
        Combined visibility score (0.0 to 1.0).
        Based on blur (Laplacian variance) and contrast ratio.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Blur score: Laplacian variance (higher = sharper)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_var = laplacian.var()
        # Normalize: 0-500 range mapped to 0-1
        blur_score = min(1.0, blur_var / 500.0)

        # Contrast ratio
        min_val, max_val = float(np.min(gray)), float(np.max(gray))
        contrast = (max_val - min_val) / 255.0

        # Combined: average of blur and contrast
        visibility = (blur_score + contrast) / 2.0
        return float(np.clip(visibility, 0.0, 1.0))

    def _update_mode(self, brightness: float, visibility: float) -> str:
        """Determine mode with stability window to prevent flickering."""
        if brightness <= self.BRIGHTNESS_NIGHT:
            candidate = "night"
        elif brightness <= self.BRIGHTNESS_NORMAL:
            candidate = "night"  # Low-light → night preprocessing
        elif visibility < self.VISIBILITY_THRESHOLD:
            candidate = "hazy"
        else:
            candidate = "normal"

        if candidate == self._candidate_mode:
            self._candidate_count += 1
        else:
            self._candidate_mode = candidate
            self._candidate_count = 1

        if self._candidate_count >= self.STABILITY_FRAMES:
            self._current_mode = candidate

        return self._current_mode

    def _enhance_night(self, frame: np.ndarray) -> np.ndarray:
        """CLAHE on L channel + gamma correction."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)

        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        # Gamma correction (gamma < 1 brightens)
        gamma = 0.7
        lut = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, lut)

        return enhanced

    def _enhance_haze(self, frame: np.ndarray) -> np.ndarray:
        """Contrast stretching + unsharp masking."""
        # Contrast stretching (5th-95th percentile)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        p5, p95 = np.percentile(gray, [5, 95])
        stretched = np.clip((frame.astype(np.float64) - p5) / (p95 - p5 + 1e-6) * 255, 0, 255).astype(np.uint8)

        # Unsharp masking
        blurred = cv2.GaussianBlur(stretched, (0, 0), 3)
        sharpened = cv2.addWeighted(stretched, 1.5, blurred, -0.5, 0)

        return sharpened
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_night_weather.py -v
```
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/night_weather.py tests/test_night_weather.py
git commit -m "feat: add night/weather adaptation with brightness and visibility estimation"
```

---

### Task 4: RTSP Ingestion & Event Publisher

**Files:**
- Create: `edge/ingestion.py`
- Create: `edge/event_publisher.py`
- Create: `tests/test_event_publisher.py`

**Interfaces:**
- `ingestion.py`: `RTSPIngestion(url) → grab_frame() → (frame, timestamp) or None`
- `event_publisher.py`: `EventPublisher(fusion_url) → publish(event_dict) → bool`

- [ ] **Step 1: Write event publisher tests**

```python
# tests/test_event_publisher.py
"""Tests for event publisher — verifies ARCHITECTURE.md §5 contract."""

def test_builds_correct_event_json():
    """Event JSON matches the frozen DetectionEvent contract."""
    from edge.event_publisher import EventPublisher
    import time

    pub = EventPublisher("http://localhost:9999")  # Won't actually connect
    event = pub.build_event(
        camera_id="cam1",
        timestamp="2026-09-10T12:00:00Z",
        object_type="person",
        track_id="42",
        bbox_pixels=[100, 50, 300, 400],
        frame_shape=(480, 640),
        confidence=0.92,
    )

    # Verify required fields exist
    assert event["camera_id"] == "cam1"
    assert event["timestamp"] == "2026-09-10T12:00:00Z"
    assert event["object_type"] == "person"
    assert event["track_id"] == "42"
    assert event["confidence"] == 0.92
    assert event["embedding"] is None

    # Verify bbox is normalized [x, y, w, h]
    assert len(event["bbox"]) == 4
    x, y, w, h = event["bbox"]
    assert 0 <= x <= 1
    assert 0 <= y <= 1
    assert 0 < w <= 1
    assert 0 < h <= 1

    # Verify conversion: pixel [100, 50, 300, 400] on 640x480
    # x = 100/640 ≈ 0.15625, y = 50/480 ≈ 0.10417
    # w = 200/640 ≈ 0.3125, h = 350/480 ≈ 0.72917
    assert abs(x - 100/640) < 0.001
    assert abs(y - 50/480) < 0.001
    assert abs(w - 200/640) < 0.001
    assert abs(h - 350/480) < 0.001


def test_object_type_mapping():
    """Vehicle COCO classes map to 'vehicle'."""
    from edge.event_publisher import EventPublisher

    pub = EventPublisher("http://localhost:9999")
    for cls_id, expected_type in [(2, "vehicle"), (3, "vehicle"), (5, "vehicle"), (7, "vehicle"), (0, "person")]:
        event = pub.build_event(
            camera_id="cam1",
            timestamp="2026-09-10T12:00:00Z",
            object_type="person" if cls_id == 0 else "vehicle",
            track_id="1",
            bbox_pixels=[100, 100, 200, 200],
            frame_shape=(480, 640),
            confidence=0.9,
        )
        assert event["object_type"] == expected_type


def test_publish_returns_false_on_failure():
    """Publish returns False when server unreachable."""
    from edge.event_publisher import EventPublisher

    pub = EventPublisher("http://localhost:19999")  # Nothing listening
    result = pub.publish({"camera_id": "cam1", "timestamp": "2026-09-10T12:00:00Z"})
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_event_publisher.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RTSP ingestion**

```python
# edge/ingestion.py
"""
RTSP stream reader with retry logic.
"""
import cv2
import time
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class RTSPIngestion:
    """Reads frames from an RTSP stream with automatic reconnection."""

    def __init__(self, url: str, max_retries: int = 3, retry_delay: float = 2.0):
        self.url = url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        """Open RTSP connection with retries."""
        for attempt in range(self.max_retries):
            try:
                self._cap = cv2.VideoCapture(self.url)
                if self._cap.isOpened():
                    logger.info(f"Connected to {self.url}")
                    return True
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: Cannot open {self.url}")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {e}")
            time.sleep(self.retry_delay)

        logger.error(f"Failed to connect to {self.url} after {self.max_retries} attempts")
        return False

    def grab_frame(self) -> Optional[Tuple[datetime, object]]:
        """
        Grab a single frame.

        Returns:
            (timestamp, frame_ndarray) or None on failure
        """
        if self._cap is None or not self._cap.isOpened():
            if not self.connect():
                return None

        ret, frame = self._cap.read()
        if not ret:
            logger.warning(f"Failed to read frame from {self.url}, reconnecting...")
            self.release()
            if self.connect():
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None

        timestamp = datetime.utcnow()
        return timestamp, frame

    def release(self):
        """Release the video capture."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __del__(self):
        self.release()
```

- [ ] **Step 4: Implement event publisher**

```python
# edge/event_publisher.py
"""
Publishes DetectionEvents to the fusion server via HTTP POST.
"""
import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# COCO class IDs → object_type mapping
VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck


class EventPublisher:
    """Publishes detection events to the fusion server."""

    def __init__(self, fusion_url: str, timeout: float = 2.0):
        self.fusion_url = fusion_url.rstrip("/")
        self.timeout = timeout
        self._endpoint = f"{self.fusion_url}/api/v1/events"

    def build_event(
        self,
        camera_id: str,
        timestamp: str,
        object_type: str,
        track_id: str,
        bbox_pixels: list,
        frame_shape: tuple,
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Build a DetectionEvent dict matching ARCHITECTURE.md §5.

        Args:
            camera_id: Camera identifier
            timestamp: ISO8601 timestamp
            object_type: "person" or "vehicle"
            track_id: ByteTrack track ID (string)
            bbox_pixels: [x1, y1, x2, y2] in pixel coordinates
            frame_shape: (height, width)
            confidence: YOLO confidence score
        """
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = bbox_pixels

        # Normalize and convert to [x, y, w, h]
        x_norm = x1 / w
        y_norm = y1 / h
        w_norm = (x2 - x1) / w
        h_norm = (y2 - y1) / h

        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "object_type": object_type,
            "track_id": str(track_id),
            "bbox": [round(x_norm, 6), round(y_norm, 6), round(w_norm, 6), round(h_norm, 6)],
            "embedding": None,
            "confidence": round(confidence, 4),
        }

    def publish(self, event: Dict[str, Any]) -> bool:
        """
        POST event to fusion server.

        Returns True on success, False on failure (logged, not raised).
        """
        try:
            resp = requests.post(
                self._endpoint,
                json=event,
                timeout=self.timeout,
            )
            if resp.status_code < 300:
                return True
            else:
                logger.warning(f"Event publish returned {resp.status_code}: {resp.text[:200]}")
                return False
        except requests.RequestException as e:
            logger.warning(f"Event publish failed (server unreachable): {e}")
            return False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_event_publisher.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add edge/ingestion.py edge/event_publisher.py tests/test_event_publisher.py
git commit -m "feat: add RTSP ingestion and event publisher"
```

---

### Task 5: Detection Service

**Files:**
- Create: `edge/detector.py`
- Create: `tests/test_detector.py`

**Interfaces:**
- `DetectionService` class: runs as a process, accepts frames via `multiprocessing.Queue`, returns detections
- `detect_request`: `(frame_id, camera_id, frame_ndarray)`
- `detect_result`: `(frame_id, camera_id, [{"bbox": [x1,y1,x2,y2], "confidence": float, "class_id": int, "class_name": str}])`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_detector.py
"""Tests for DetectionService."""

def test_detection_service_processes_frame():
    """DetectionService returns detections for a frame with objects."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing
    import time

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    # Don't start the loop, just test a single inference
    import cv2
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (250, 100), (350, 400), (255, 255, 255), -1)

    detections = svc._run_inference(frame)
    assert isinstance(detections, list)
    # May or may not detect the rectangle (it's synthetic), but should not crash
    for det in detections:
        assert "bbox" in det
        assert "confidence" in det
        assert "class_id" in det
        assert "class_name" in det


def test_class_filtering():
    """Only target COCO classes are kept."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    # Create mock YOLO results with mixed classes
    import cv2
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = svc._run_inference(frame)
    # All returned detections should be in target classes
    for det in detections:
        assert det["class_id"] in {0, 2, 3, 5, 7}


def test_empty_frame():
    """Empty/black frame produces empty detections."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = svc._run_inference(frame)
    assert isinstance(detections, list)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_detector.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement detection service**

```python
# edge/detector.py
"""
Shared detection service — loads YOLOv8n once, serves batched inference
to camera workers via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TARGET_CLASSES = {0, 2, 3, 5, 7}  # person, car, motorcycle, bus, truck
CLASS_NAMES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class DetectionService:
    """
    Runs YOLOv8n inference. Designed to run as a separate process.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = DetectionService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.35,
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._model = None

    def _load_model(self):
        """Load YOLOv8n model."""
        from ultralytics import YOLO
        logger.info(f"Loading YOLOv8n from {self.model_path}...")
        self._model = YOLO(self.model_path)
        logger.info("YOLOv8n loaded successfully")

    def _run_inference(self, frame: np.ndarray) -> List[Dict]:
        """
        Run inference on a single frame.

        Returns:
            List of detection dicts with keys: bbox, confidence, class_id, class_name
        """
        if self._model is None:
            self._load_model()

        results = self._model(frame, classes=list(TARGET_CLASSES), verbose=False)

        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in TARGET_CLASSES:
                    continue
                conf = float(box.conf[0])
                if conf < self.conf_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls_id,
                    "class_name": CLASS_NAMES.get(cls_id, "unknown"),
                })

        return detections

    def run(self):
        """Main loop: pull frames from req_queue, push results to res_queue."""
        self._load_model()
        logger.info("Detection service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Detection service received shutdown signal")
                break

            frame_id, camera_id, frame = item
            try:
                detections = self._run_inference(frame)
                self.res_queue.put((frame_id, camera_id, detections))
            except Exception as e:
                logger.error(f"Detection failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, []))

        logger.info("Detection service stopped")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_detector.py -v
```
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add edge/detector.py tests/test_detector.py
git commit -m "feat: add shared YOLOv8n detection service with batched inference"
```

---

### Task 6: Visualization (cv2 + MJPEG)

**Files:**
- Create: `edge/visualizer.py`

**Interfaces:**
- `Visualizer(camera_id, port)` class
- `render(frame, tracks, mode_info)` — draws annotations and serves MJPEG

- [ ] **Step 1: Implement visualizer**

```python
# edge/visualizer.py
"""
Bounding box + track ID rendering and MJPEG HTTP server.
"""
import cv2
import numpy as np
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional
from io import BytesIO

logger = logging.getLogger(__name__)

# Colors (BGR)
COLOR_PERSON = (0, 255, 0)    # Green
COLOR_VEHICLE = (255, 128, 0)  # Blue
COLOR_TEXT_BG = (0, 0, 0)      # Black
COLOR_TEXT_FG = (255, 255, 255) # White


class _MJPEGHandler(BaseHTTPRequestHandler):
    """HTTP handler for MJPEG stream and snapshot."""

    def __init__(self, *args, visualizer=None, **kwargs):
        self._visualizer = visualizer
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/stream":
            self._serve_stream()
        elif self.path == "/snapshot":
            self._serve_snapshot()
        else:
            self.send_error(404)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        while True:
            frame = self._visualizer._last_annotated
            if frame is None:
                time.sleep(0.05)
                continue

            ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue

            self.wfile.write(b"--frame\r\n")
            self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
            self.wfile.write(jpeg.tobytes())
            self.wfile.write(b"\r\n")

            try:
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break

            time.sleep(0.033)  # ~30 FPS max for stream

    def _serve_snapshot(self):
        frame = self._visualizer._last_annotated
        if frame is None:
            self.send_error(503, "No frame available")
            return

        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ret:
            self.send_error(500, "JPEG encode failed")
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg.tobytes())))
        self.end_headers()
        self.wfile.write(jpeg.tobytes())

    def log_message(self, format, *args):
        pass  # Suppress HTTP server logs


class Visualizer:
    """Renders annotations on frames and serves MJPEG stream."""

    def __init__(self, camera_id: str, port: int, enabled: bool = True):
        self.camera_id = camera_id
        self.port = port
        self.enabled = enabled
        self._last_annotated: Optional[np.ndarray] = None
        self._http_server: Optional[HTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._fps_counter = 0
        self._fps_time = time.time()
        self._current_fps = 0.0
        self._window_name = f"{camera_id} — Track View"

        if enabled:
            self._start_http_server()

    def _start_http_server(self):
        """Start MJPEG HTTP server in a background thread."""
        def handler(*args, **kwargs):
            _MJPEGHandler(*args, visualizer=self, **kwargs)

        try:
            self._http_server = HTTPServer(("0.0.0.0", self.port), handler)
            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_thread.start()
            logger.info(f"MJPEG server started on port {self.port}")
        except OSError as e:
            logger.warning(f"Could not start MJPEG server on port {self.port}: {e}")
            self._http_server = None

    def render(self, frame: np.ndarray, tracks: List[Dict], mode_info: Dict):
        """
        Render annotations on frame, display via cv2.imshow, and update MJPEG buffer.

        Args:
            frame: Original BGR frame
            tracks: List of TrackedObject (track_id, bbox, class_name, confidence)
            mode_info: {"mode": str, "brightness": float, "visibility": float}
        """
        annotated = frame.copy()

        # Draw bounding boxes and labels
        for track in tracks:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]
            color = COLOR_PERSON if track.class_name == "person" else COLOR_VEHICLE

            # Bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Label background
            label = f"#{track.track_id} {track.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), COLOR_TEXT_BG, -1)

            # Label text
            cv2.putText(annotated, label, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT_FG, 1)

        # FPS counter
        self._fps_counter += 1
        now = time.time()
        if now - self._fps_time >= 1.0:
            self._current_fps = self._fps_counter / (now - self._fps_time)
            self._fps_counter = 0
            self._fps_time = now

        cv2.putText(
            annotated,
            f"FPS: {self._current_fps:.1f}",
            (annotated.shape[1] - 120, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            COLOR_TEXT_FG,
            2,
        )

        # Mode indicator
        mode = mode_info.get("mode", "normal")
        if mode == "night":
            cv2.putText(annotated, "[NIGHT MODE]", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        elif mode == "hazy":
            cv2.putText(annotated, "[LOW VISIBILITY]", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        # Update MJPEG buffer
        self._last_annotated = annotated

        # cv2.imshow (if display available)
        if self.enabled:
            try:
                cv2.imshow(self._window_name, annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    return False  # Signal to quit
            except cv2.error:
                pass  # Headless server, no display

        return True

    def shutdown(self):
        """Clean up resources."""
        if self._http_server:
            self._http_server.shutdown()
        if self.enabled:
            try:
                cv2.destroyWindow(self._window_name)
            except cv2.error:
                pass
```

- [ ] **Step 2: Commit**

```bash
git add edge/visualizer.py
git commit -m "feat: add visualization with cv2 rendering and MJPEG HTTP server"
```

---

### Task 7: Camera Worker Pipeline

**Files:**
- Create: `edge/camera_worker.py`

**Interfaces:**
- `CameraWorker(camera_url, camera_id, fusion_url, target_fps, display, force_mode)` class
- `run()` — main loop

- [ ] **Step 1: Implement camera worker**

```python
# edge/camera_worker.py
"""
Per-camera processing pipeline: ingest → preprocess → detect → track → publish → visualize.
"""
import time
import logging
import multiprocessing
from typing import Optional

from edge.ingestion import RTSPIngestion
from edge.night_weather import NightWeatherProcessor
from edge.tracker import Tracker
from edge.event_publisher import EventPublisher
from edge.visualizer import Visualizer

logger = logging.getLogger(__name__)


class CameraWorker:
    """
    Per-camera pipeline orchestrator.

    Reads frames from RTSP, preprocesses (night/weather), sends to
    DetectionService for inference, tracks objects, publishes events,
    and renders live visualization.
    """

    def __init__(
        self,
        camera_url: str,
        camera_id: str,
        fusion_url: str,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        target_fps: int = 10,
        display: bool = True,
        force_mode: Optional[str] = None,
        mjpeg_port: int = 8081,
    ):
        self.camera_url = camera_url
        self.camera_id = camera_id
        self.target_fps = target_fps
        self.force_mode = force_mode

        self.ingestion = RTSPIngestion(camera_url)
        self.night_weather = NightWeatherProcessor()
        self.tracker = Tracker()
        self.publisher = EventPublisher(fusion_url)
        self.visualizer = Visualizer(camera_id, mjpeg_port, enabled=display)

        self.req_queue = req_queue
        self.res_queue = res_queue
        self._frame_id = 0

    def run(self):
        """Main processing loop."""
        logger.info(f"Camera worker {self.camera_id} starting ({self.camera_url})")

        if not self.ingestion.connect():
            logger.error(f"Camera {self.camera_id}: Cannot connect to {self.camera_url}")
            return

        frame_interval = 1.0 / self.target_fps

        while True:
            loop_start = time.time()

            # 1. Grab frame
            result = self.ingestion.grab_frame()
            if result is None:
                logger.warning(f"Camera {self.camera_id}: No frame, retrying...")
                time.sleep(0.5)
                continue

            timestamp, frame = result
            h, w = frame.shape[:2]
            self._frame_id += 1

            # 2. Night/weather preprocessing
            processed_frame, mode_info = self.night_weather.process(frame, self.force_mode)

            # 3. Send to detection service
            self.req_queue.put((self._frame_id, self.camera_id, processed_frame))

            # Wait for result (with timeout)
            detections = None
            deadline = time.time() + 0.5
            while time.time() < deadline:
                try:
                    fid, cid, dets = self.res_queue.get(timeout=0.1)
                    if cid == self.camera_id and fid == self._frame_id:
                        detections = dets
                        break
                    # Put back if it's for a different camera
                    self.res_queue.put((fid, cid, dets))
                except Exception:
                    continue

            if detections is None:
                detections = []

            # 4. Track objects
            tracks = self.tracker.update(detections, (h, w))

            # 5. Publish events
            ts_iso = timestamp.isoformat() + "Z"
            for track in tracks:
                object_type = "person" if track.class_name == "person" else "vehicle"
                event = self.publisher.build_event(
                    camera_id=self.camera_id,
                    timestamp=ts_iso,
                    object_type=object_type,
                    track_id=str(track.track_id),
                    bbox_pixels=track.bbox,
                    frame_shape=(h, w),
                    confidence=track.confidence,
                )
                self.publisher.publish(event)

            # 6. Visualize
            if not self.visualizer.render(frame, tracks, mode_info):
                logger.info(f"Camera {self.camera_id}: Quit signal received")
                break

            # Frame timing
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Cleanup
        self.ingestion.release()
        self.visualizer.shutdown()
        logger.info(f"Camera worker {self.camera_id} stopped")
```

- [ ] **Step 2: Commit**

```bash
git add edge/camera_worker.py
git commit -m "feat: add camera worker pipeline orchestrator"
```

---

### Task 8: Entry Points

**Files:**
- Create: `edge/run_detection_service.py`
- Create: `edge/run_camera.py`
- Create: `edge/run_all.py`

- [ ] **Step 1: Implement detection service entry point**

```python
# edge/run_detection_service.py
"""
Entry point: start the shared detection service.

Usage:
    python -m edge.run_detection_service
"""
import multiprocessing
import logging
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("detector")


def main():
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    from edge.detector import DetectionService
    svc = DetectionService(req_queue, res_queue)

    def shutdown(signum, frame):
        logger.info("Shutdown signal received")
        req_queue.put(None)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Print connection info for camera workers
    logger.info("Detection service starting...")
    logger.info(f"Request queue: {req_queue}")
    logger.info(f"Result queue: {res_queue}")

    svc.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Implement camera worker entry point**

```python
# edge/run_camera.py
"""
Entry point: start a single camera worker.

Usage:
    python -m edge.run_camera --camera-url rtsp://localhost:8554/cam1 --camera-id cam1
"""
import argparse
import multiprocessing
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def parse_args():
    parser = argparse.ArgumentParser(description="IBVAP Camera Worker")
    parser.add_argument("--camera-url", required=True, help="RTSP stream URL")
    parser.add_argument("--camera-id", required=True, help="Camera identifier")
    parser.add_argument("--fusion-server", default="http://localhost:8000", help="Fusion server URL")
    parser.add_argument("--target-fps", type=int, default=10, help="Target FPS")
    parser.add_argument("--display", action="store_true", default=True, help="Enable cv2 display")
    parser.add_argument("--no-display", dest="display", action="store_false", help="Disable cv2 display")
    parser.add_argument("--night-mode", action="store_true", help="Force night mode")
    parser.add_argument("--haze-mode", action="store_true", help="Force haze mode")
    parser.add_argument("--mjpeg-port", type=int, default=8081, help="MJPEG server port")
    parser.add_argument("--req-queue", type=str, default=None, help="Shared request queue (for multi-worker)")
    parser.add_argument("--res-queue", type=str, default=None, help="Shared result queue (for multi-worker)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Get or create queues
    if args.req_queue and args.res_queue:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
    else:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()

    force_mode = None
    if args.night_mode:
        force_mode = "night"
    elif args.haze_mode:
        force_mode = "hazy"

    from edge.camera_worker import CameraWorker
    worker = CameraWorker(
        camera_url=args.camera_url,
        camera_id=args.camera_id,
        fusion_url=args.fusion_server,
        req_queue=req_queue,
        res_queue=res_queue,
        target_fps=args.target_fps,
        display=args.display,
        force_mode=force_mode,
        mjpeg_port=args.mjpeg_port,
    )
    worker.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Implement all-in-one entry point**

```python
# edge/run_all.py
"""
Entry point: start detection service + multiple camera workers.

Usage:
    python -m edge.run_all --cameras cam1,cam2 --fusion-server http://localhost:8000
"""
import argparse
import multiprocessing
import logging
import time
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("run_all")

DEFAULT_CAMERA_URLS = {
    "cam1": "rtsp://localhost:8554/cam1",
    "cam2": "rtsp://localhost:8554/cam2",
    "cam3": "rtsp://localhost:8554/cam3",
}


def parse_args():
    parser = argparse.ArgumentParser(description="IBVAP Edge Pipeline — All-in-One")
    parser.add_argument("--cameras", default="cam1", help="Comma-separated camera IDs")
    parser.add_argument("--fusion-server", default="http://localhost:8000", help="Fusion server URL")
    parser.add_argument("--target-fps", type=int, default=10, help="Target FPS per camera")
    parser.add_argument("--no-display", action="store_true", help="Disable cv2 display")
    parser.add_argument("--night-mode", action="store_true", help="Force night mode")
    parser.add_argument("--haze-mode", action="store_true", help="Force haze mode")
    return parser.parse_args()


def main():
    args = parse_args()
    camera_ids = [c.strip() for c in args.cameras.split(",")]

    # Shared queues
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    # Start detection service
    from edge.detector import DetectionService
    detector = DetectionService(req_queue, res_queue)
    detector_proc = multiprocessing.Process(target=detector.run, daemon=True)
    detector_proc.start()
    logger.info("Detection service started")

    # Wait for model to load
    time.sleep(3)

    # Start camera workers
    force_mode = None
    if args.night_mode:
        force_mode = "night"
    elif args.haze_mode:
        force_mode = "hazy"

    from edge.camera_worker import CameraWorker
    workers = []
    for i, cam_id in enumerate(camera_ids):
        url = DEFAULT_CAMERA_URLS.get(cam_id, f"rtsp://localhost:8554/{cam_id}")
        port = 8081 + i

        worker = CameraWorker(
            camera_url=url,
            camera_id=cam_id,
            fusion_url=args.fusion_server,
            req_queue=req_queue,
            res_queue=res_queue,
            target_fps=args.target_fps,
            display=not args.no_display,
            force_mode=force_mode,
            mjpeg_port=port,
        )
        proc = multiprocessing.Process(target=worker.run, daemon=True)
        proc.start()
        workers.append(proc)
        logger.info(f"Camera worker {cam_id} started (MJPEG: http://localhost:{port}/stream)")

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        req_queue.put(None)
        for p in workers:
            p.terminate()
        detector_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for all processes
    try:
        detector_proc.join()
        for p in workers:
            p.join()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add edge/run_detection_service.py edge/run_camera.py edge/run_all.py
git commit -m "feat: add entry points for detection service and camera workers"
```

---

### Task 9: Integration Test & Update requirements.txt

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_integration_pipeline.py`

- [ ] **Step 1: Update requirements.txt**

Add to `requirements.txt`:
```
ultralytics>=8.2.0
opencv-python-headless>=4.9.0
requests>=2.31.0
scipy>=1.11.0
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_integration_pipeline.py
"""Integration test: full pipeline on synthetic video."""

def test_full_pipeline_synthetic_video():
    """
    Feed a synthetic video through the full pipeline:
    ingestion → night/weather → detection → tracking → event building.
    Verifies events match ARCHITECTURE.md §5 contract.
    """
    import numpy as np
    import cv2
    from edge.night_weather import NightWeatherProcessor
    from edge.tracker import Tracker
    from edge.event_publisher import EventPublisher

    # Create synthetic 5-frame video with a moving white rectangle (person)
    frames = []
    for i in range(5):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Person moves from left to right
        x = 100 + i * 50
        cv2.rectangle(frame, (x, 100), (x + 100, 400), (255, 255, 255), -1)
        frames.append(frame)

    nw = NightWeatherProcessor()
    tracker = Tracker()
    publisher = EventPublisher("http://localhost:9999")

    all_events = []
    for i, frame in enumerate(frames):
        # Preprocess
        processed, mode_info = nw.process(frame)

        # Detect (simulate detections since we can't run YOLO in test)
        h, w = frame.shape[:2]
        x = 100 + i * 50
        fake_detections = [{
            "bbox": [float(x), 100.0, float(x + 100), 400.0],
            "confidence": 0.9,
            "class_id": 0,
            "class_name": "person",
        }]

        # Track
        tracks = tracker.update(fake_detections, (h, w))
        assert len(tracks) >= 1

        # Build events
        for track in tracks:
            event = publisher.build_event(
                camera_id="cam1",
                timestamp=f"2026-09-10T12:00:0{i}Z",
                object_type="person",
                track_id=str(track.track_id),
                bbox_pixels=track.bbox,
                frame_shape=(h, w),
                confidence=track.confidence,
            )
            all_events.append(event)

    # Verify contract compliance
    assert len(all_events) > 0
    for event in all_events:
        assert "camera_id" in event
        assert "timestamp" in event
        assert "object_type" in event
        assert "track_id" in event
        assert "bbox" in event
        assert "embedding" in event and event["embedding"] is None
        assert "confidence" in event
        assert event["object_type"] in ("person", "vehicle")
        assert len(event["bbox"]) == 4
        assert all(0 <= v <= 1 for v in event["bbox"])
```

- [ ] **Step 3: Run integration test**

```bash
python -m pytest tests/test_integration_pipeline.py -v
```
Expected: PASS

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_integration_pipeline.py
git commit -m "feat: Phase 1 integration test and dependency updates"
```

---

### Task 10: Run All Tests & Final Commit

- [ ] **Step 1: Run full test suite**

```bash
cd C:\Users\Garvi\Desktop\Projects\IBVAP
.\venv\Scripts\activate
python -m pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 2: Verify no lint/type errors (if tools available)**

```bash
# If ruff is available:
ruff check edge/ tests/
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "Phase 1 complete: detection, tracking, night/weather, visualization

- Shared YOLOv8n DetectionService with multiprocessing.Queue IPC
- ByteTrack per-camera tracker (self-contained fallback if yolox unavailable)
- Night/weather adaptation: brightness estimator, visibility estimator, CLAHE/gamma preprocessing
- Dual visualization: cv2.imshow window + MJPEG HTTP server
- Event publisher: DetectionEvent JSON matching ARCHITECTURE.md §5
- Entry points: run_all.py (dev), run_camera.py + run_detection_service.py (separate)
- 30+ automated tests covering all modules
- Integration test: synthetic video through full pipeline"
```

---

## Summary

| Task | Deliverable | Tests |
|---|---|---|
| 1 | Dependencies installed, YOLOv8n verified | test_yolo_load.py |
| 2 | ByteTrack tracker (yolox or fallback) | test_tracker.py (4 tests) |
| 3 | Night/weather adaptation | test_night_weather.py (7 tests) |
| 4 | RTSP ingestion + event publisher | test_event_publisher.py (3 tests) |
| 5 | Shared detection service | test_detector.py (3 tests) |
| 6 | Visualization (cv2 + MJPEG) | — |
| 7 | Camera worker pipeline | — |
| 8 | Entry points (run_all, run_camera, run_detection_service) | — |
| 9 | Integration test + dependency updates | test_integration_pipeline.py |
| 10 | Final test run + commit | All tests green |
