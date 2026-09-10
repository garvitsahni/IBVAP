# Phase 1 — Detection & Tracking: Design Spec

**Date:** 2026-09-10
**Status:** Approved for implementation
**Scope:** Features #1 (Human detection & tracking), #2 (Vehicle detection & classification), #7 (Night-time detection), #23 (Weather-adaptive detection)

---

## 1. Objective

Build the edge processing pipeline: ingest RTSP streams, detect persons/vehicles with YOLOv8n, track them with ByteTrack, publish DetectionEvents to the fusion server, and render live visualizations (cv2 + web MJPEG).

**Exit criteria (from PHASES.md):** Walk in front of a real/simulated camera, see a bounding box + track ID rendered in real time, at both normal and low-light/simulated-poor-visibility conditions.

---

## 2. Architecture: Shared Detection Service (Approach B)

One shared `DetectionService` process runs YOLOv8n and serves batched inference to multiple per-camera `CameraWorker` processes. Each camera worker handles ingestion, preprocessing, tracking, publishing, and visualization independently.

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  CameraWorker │   │  CameraWorker │   │  CameraWorker │
│    (cam1)     │   │    (cam2)     │   │    (cam3)     │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │ Queue            │ Queue            │ Queue
       ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────┐
│              DetectionService (YOLOv8n)               │
│   Input Queue ← batched frames → Output Queue         │
└─────────────────────────────────────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
  POST /events       POST /events       POST /events
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                  Fusion Server (FastAPI)               │
└─────────────────────────────────────────────────────┘
```

**Why shared detection:** YOLOv8n model (~6MB) loaded once. Batch inference across cameras is faster than N sequential single-frame calls. Per-camera ByteTrack stays independent (track IDs are camera-local).

---

## 3. Module Structure

```
edge/
├── __init__.py
├── detector.py              # DetectionService: shared YOLOv8n process
├── tracker.py               # ByteTrack per-camera tracker wrapper
├── camera_worker.py         # Per-camera pipeline orchestrator
├── night_weather.py         # Brightness/visibility estimators + preprocessing
├── ingestion.py             # RTSP stream reader (OpenCV VideoCapture)
├── event_publisher.py       # HTTP POST DetectionEvent to fusion server
├── visualizer.py            # Bbox + track ID rendering + MJPEG server
├── run_camera.py            # Entry point: single camera worker
├── run_detection_service.py # Entry point: detection service process
└── run_all.py               # Entry point: spawns service + all cameras
```

---

## 4. Component Designs

### 4.1 DetectionService (`detector.py`)

**Responsibility:** Load YOLOv8n once, accept batched frames, run inference, return detections.

**IPC via multiprocessing.Queue:**
- `detect_requests: Queue[(frame_id, camera_id, frame_ndarray)]`
- `detect_results: Queue[(frame_id, camera_id, detections_list)]`

**Inference loop:**
1. Check input queue for pending frames
2. If multiple frames pending, batch them into one YOLO call
3. If one frame pending, run immediately (don't wait for batch)
4. Push results to output queue

**Class filtering:** Keep only COCO classes: 0 (person), 2 (car), 3 (motorcycle), 5 (bus), 7 (truck). Drop all others.

**Detection format:**
```python
{
    "bbox": [x1, y1, x2, y2],  # pixel coordinates
    "confidence": float,
    "class_id": int,
    "class_name": str,  # "person" | "car" | "motorcycle" | "bus" | "truck"
}
```

**Object type mapping:** COCO class 0 → `"person"`, all vehicle classes → `"vehicle"` (matches ARCHITECTURE.md §5 `object_type` field).

**Shutdown:** Camera workers push a sentinel `None` value. Detection service exits its loop on receiving it.

### 4.2 CameraWorker (`camera_worker.py`)

**Main loop (per-frame):**
```
1. frame = ingestion.grab_frame()           # RTSP read
2. frame, mode_info = night_weather.process(frame)  # Preprocess
3. detections = detection_service.detect(frame_id, frame)  # Send, wait for result
4. tracks = tracker.update(detections)       # ByteTrack
5. for track in tracks:
       event = build_detection_event(track, camera_id, mode_info)
       event_publisher.publish(event)        # POST to fusion server
6. visualizer.render(frame, tracks, mode_info)  # cv2 + MJPEG
```

**Frame timing:** Target 10 FPS. If processing exceeds 100ms, skip the frame. Never queue up frames — drop rather than lag.

**Tracker lifecycle:** ByteTrack maintains track IDs per camera. A track unmatched for 30 consecutive frames is removed (object exited frame).

**Error handling:**
- RTSP drop: retry 3x with 2s backoff. Permanent failure → log error, exit worker.
- Fusion server unreachable: log warnings, keep processing locally. Publishing is best-effort in Phase 1.
- Detection timeout: if no result within 500ms, skip visualization for that frame.

### 4.3 Night/Weather Adaptation (`night_weather.py`)

**Brightness estimator:**
- Convert frame to grayscale, compute mean pixel intensity
- Thresholds:
  - `mean > 80`: Normal mode
  - `30 < mean <= 80`: Low-light mode (CLAHE enhancement)
  - `mean <= 30`: Night mode (aggressive CLAHE + gamma correction)

**Visibility estimator:**
- **Blur score:** Laplacian variance of grayscale frame. Low variance = blurry/hazy.
- **Contrast ratio:** `(max_intensity - min_intensity) / 255`. Low = fog/haze.
- Combined visibility score: `0.0` (invisible) to `1.0` (perfect). When visibility < 0.4, flag detections as low-confidence.

**Preprocessing transforms:**
- **Night:** CLAHE on L channel in LAB color space (clipLimit=3.0), then gamma correction (γ=0.7).
- **Haze:** Contrast stretching (5th-95th percentile normalization) + unsharp masking.
- **Normal:** No transform (passthrough).

**Mode stability:** Require 5 consecutive frames in the new state before switching modes. Prevents flickering at brightness boundaries.

**Output:** `(processed_frame, {"mode": "normal"|"night"|"hazy", "brightness": float, "visibility": float})`

### 4.4 Visualization (`visualizer.py`)

**Dual output — both active simultaneously:**

**1. cv2.imshow window:**
- One window per camera, titled `{camera_id} — Track View`
- Bounding boxes: green for person, blue for vehicle
- Labels: `#{track_id}` + confidence, top-left of bbox
- FPS counter: top-right corner, updated every 30 frames
- Mode indicator: `[NIGHT MODE]` or `[LOW VISIBILITY]` when active
- Press `q` to close that window
- Skipped gracefully if no display available (headless server)

**2. MJPEG HTTP server:**
- Per-camera HTTP server on port `8080 + camera_index` (cam1→8081, cam2→8082)
- `/stream` — multipart MJPEG stream (viewable in any browser)
- `/snapshot` — single JPEG frame
- Uses Python `http.server` + threading. No extra dependencies.
- Annotated frames encoded as JPEG at quality 80

---

## 5. Entry Points

### 5.1 Development mode (all-in-one)
```bash
python -m edge.run_all --cameras cam1,cam2 --fusion-server http://localhost:8000
```
Spawns DetectionService + CameraWorker processes. Easiest demo startup.

### 5.2 Separate mode (debug individual cameras)
```bash
# Terminal 1
python -m edge.run_detection_service

# Terminal 2+
python -m edge.run_camera --camera-url rtsp://localhost:8554/cam1 --camera-id cam1 --fusion-server http://localhost:8000
```

### 5.3 CLI arguments
| Argument | Default | Description |
|---|---|---|
| `--camera-url` | (required) | RTSP stream URL |
| `--camera-id` | (required) | Camera identifier |
| `--fusion-server` | `http://localhost:8000` | Fusion server base URL |
| `--target-fps` | `10` | Target frame rate |
| `--display` | auto | Enable/disable cv2.imshow |
| `--night-mode` | off | Force night mode for demo |
| `--haze-mode` | off | Force haze/poor-visibility for demo |

---

## 6. Data Contract Compliance

DetectionEvents published by the edge node **must** match ARCHITECTURE.md §5:

```json
{
  "camera_id": "string",        // from --camera-id CLI arg
  "timestamp": "ISO8601",       // frame capture time
  "object_type": "person|vehicle",  // mapped from COCO class
  "track_id": "string",         // ByteTrack track ID
  "bbox": [x, y, w, h],        // normalized 0-1 (converted from pixel coords)
  "embedding": null,            // Phase 2 — not populated in Phase 1
  "confidence": float           // YOLO confidence score
}
```

Note: `bbox` is `[x, y, w, h]` normalized. Conversion from YOLO's `[x1, y1, x2, y2]` pixel format:
```
x_norm = x1 / frame_width
y_norm = y1 / frame_height
w_norm = (x2 - x1) / frame_width
h_norm = (y2 - y1) / frame_height
```

`embedding` is `null` in Phase 1 (populated in Phase 2 with OSNet/vehicle-ReID).

---

## 7. Testing

### Automated tests
- `tests/test_night_weather.py`: brightness estimator, visibility estimator, preprocessing transforms, mode stability
- `tests/test_tracker.py`: ByteTrack ID consistency, multi-object tracking, lost track cleanup
- `tests/test_detector.py`: DetectionService single/batched frames, class filtering, empty frame handling
- `tests/test_event_publisher.py`: DetectionEvent JSON matches §5 contract, graceful failure handling

### Visual QA (required per PHASES.md)
1. Start simulated cameras + detection pipeline
2. Person walks in front of cam1 → bbox + track ID visible in real time (cv2 + browser)
3. Same person walks into cam2 → new track ID assigned (cross-camera re-ID is Phase 2)
4. Force `--night-mode` → preprocessing activates, detections still work
5. Force `--haze-mode` → low-visibility flag appears, detections work with reduced confidence
6. Check `GET /api/v1/events` → events are created with correct fields

---

## 8. Dependencies

### New Python packages
```
ultralytics>=8.2.0
yolox>=0.3.0
opencv-python-headless>=4.9.0
numpy>=1.26.0
requests>=2.31.0
```

### Fallback: yolox compatibility
If `yolox` fails to install on Python 3.13/numpy 2.x, implement a self-contained ByteTrack (~200 lines): SORT-style Kalman filter + Hungarian assignment. This keeps the tracker interface identical (`tracker.update(detections) → tracked_objects`).

### No Docker/infrastructure changes
mediamtx already configured for simulated RTSP. PostgreSQL already running. No new containers needed.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| yolox won't install on Python 3.13 | ByteTrack unavailable | Self-contained reimplementation (~200 lines) |
| YOLOv8n too slow on CPU | <5 FPS, laggy demo | Configurable `--target-fps`, skip frames rather than queue |
| RTSP stream startup delays | Camera workers fail to connect | 3 retries with 2s backoff, clear error messages |
| Night preprocessing hurts detection accuracy | More false negatives at night | CLAHE is conservative; log detection counts per mode for comparison |

---

## 10. What Phase 1 Does NOT Build

- Re-ID embeddings (Phase 2)
- Cross-camera tracking (Phase 2)
- Hash-chain ledger writes (Phase 3)
- Camera tamper detection (Phase 3)
- Rule engine / alert firing (Phase 4)
- Dashboard / patrol app (Phase 5)

DetectionEvents are published to the fusion server but no alerts are generated from them yet. The fusion server stores them; Phase 2+ consumes them.
