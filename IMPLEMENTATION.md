# IBVAP — Implementation Guide

Concrete, step-by-step build instructions to accompany PRD.md / ARCHITECTURE.md / PHASES.md / AGENTS.md. This document turns the architecture into actual repo structure, dependencies, schemas, and starter code for each phase. Written for Stage 1 (laptop-only, simulated multi-camera) per ARCHITECTURE.md Section 6.

---

## 1. Repository Structure

```
ibvap/
├── README.md
├── AGENTS.md
├── ARCHITECTURE.md
├── PRD.md
├── PHASES.md
├── RULES.md
├── DESIGN_SYSTEM.md
├── IMPLEMENTATION.md
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── edge/
│   ├── ingestion.py          # RTSP stream reader
│   ├── detection.py          # YOLOv8n wrapper
│   ├── tracking.py           # ByteTrack wrapper
│   ├── reid.py                # OSNet embedding extraction
│   ├── camera_health.py      # tamper/blinding/drift detection
│   ├── night_weather.py      # brightness/visibility branching
│   └── event_publisher.py    # sends DetectionEvent to fusion server
├── fusion_server/
│   ├── main.py                # FastAPI app entrypoint
│   ├── api/
│   │   ├── events.py          # POST /events (from edge nodes)
│   │   ├── alerts.py          # GET /alerts, alert lifecycle
│   │   ├── footprint.py       # GET /footprint/{object_id}
│   │   └── watchlist.py       # watchlist CRUD + matching
│   ├── core/
│   │   ├── reid_matcher.py    # cross-camera cosine-similarity matching
│   │   ├── rule_engine.py     # ROI/geometry alert logic
│   │   ├── ledger.py          # hash-chain implementation
│   │   ├── threat_scoring.py
│   │   ├── trajectory.py      # Kalman filter projection
│   │   └── ai_enrichment.py   # async local LLM/VLM service
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schema.sql
│   │   └── session.py
│   └── storage/
│       └── clip_store.py      # local filesystem/MinIO clip writer
├── dashboard/                  # React frontend
├── patrol_app/                 # LAN-only companion client
├── scripts/
│   ├── setup_simulated_cameras.sh
│   └── verify_ledger.py
└── tests/
    ├── test_reid_matching.py
    ├── test_rule_engine.py
    └── test_ledger_integrity.py
```

---

## 2. Environment Setup (Phase 0)

### 2.1 Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary \
    ultralytics opencv-python-headless numpy \
    torch torchvision \
    filterpy \
    paddleocr paddlepaddle \
    python-multipart pydantic pydantic-settings \
    pytest httpx
```

Note: `ultralytics` ships YOLOv8n; `filterpy` provides the Kalman filter for trajectory prediction. `paddleocr`/`paddlepaddle` cover ANPR text recognition — install CPU builds for laptop-stage development.

### 2.2 Simulated Multi-Camera RTSP

Since real BOP cameras aren't available yet, use `mediamtx` to serve looped footage as RTSP streams — this is real RTSP ingestion code exercised against realistic input, not a hardcoded stub.

```bash
# scripts/setup_simulated_cameras.sh
docker run -d --name mediamtx -p 8554:8554 bluenviron/mediamtx

# Push looped footage to two simulated camera paths
ffmpeg -re -stream_loop -1 -i cam1_footage.mp4 -c copy -f rtsp rtsp://localhost:8554/cam1 &
ffmpeg -re -stream_loop -1 -i cam2_footage.mp4 -c copy -f rtsp rtsp://localhost:8554/cam2 &
```

Each engineer records or sources a short clip of themselves walking through a space, or uses a public sample surveillance clip, so re-ID has an actual person to track across "cameras" cam1 and cam2 in Phase 2.

### 2.3 Database

```bash
docker run -d --name ibvap-postgres -e POSTGRES_PASSWORD=devpass \
    -e POSTGRES_DB=ibvap -p 5432:5432 postgres:16
```

```sql
-- fusion_server/db/schema.sql
CREATE TABLE detection_events (
    id SERIAL PRIMARY KEY,
    camera_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    object_type TEXT NOT NULL,
    track_id TEXT NOT NULL,
    bbox JSONB NOT NULL,
    embedding VECTOR(512),  -- requires pgvector extension; or store as FLOAT8[]
    confidence FLOAT NOT NULL
);

CREATE TABLE footprint_entries (
    id SERIAL PRIMARY KEY,
    object_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('first_seen','hop','alert','last_seen')),
    hash TEXT NOT NULL,
    previous_hash TEXT
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    alert_id TEXT UNIQUE NOT NULL,
    object_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('fired','enriched')),
    threat_score FLOAT,
    clip_path TEXT,
    ai_explanation TEXT,
    trajectory_projection JSONB
);

CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('face','plate')),
    embedding VECTOR(512),
    added_at TIMESTAMPTZ DEFAULT now()
);
```

These three tables map directly to the frozen data contracts in ARCHITECTURE.md Section 5 — if you change a contract, update this schema in the same PR.

---

## 3. Phase 1 — Detection & Tracking

```python
# edge/detection.py
from ultralytics import YOLO

class Detector:
    def __init__(self, weights="yolov8n.pt"):
        self.model = YOLO(weights)

    def infer(self, frame):
        results = self.model(frame, classes=[0, 2])  # 0=person, 2=car (COCO)
        return results[0].boxes  # xyxy, conf, cls
```

```python
# edge/tracking.py
from yolox.tracker.byte_tracker import BYTETracker  # or `pip install bytetracker`

class Tracker:
    def __init__(self):
        self.tracker = BYTETracker(track_thresh=0.5, match_thresh=0.8)

    def update(self, detections, img_size):
        return self.tracker.update(detections, img_size, img_size)
```

Night/weather branching (edge/night_weather.py) computes mean frame brightness and a simple visibility heuristic (Laplacian variance for blur/haze) before each detection call, swapping in enhanced preprocessing when thresholds are crossed. Keep this as a preprocessing decorator around `Detector.infer`, not a separate pipeline, so Phase 1 stays a single code path.

**Exit test:** run `python edge/ingestion.py --camera rtsp://localhost:8554/cam1` and confirm bounding boxes render on a live `cv2.imshow` window with track IDs persisting across frames.

---

## 4. Phase 2 — Cross-Camera Identity

```python
# edge/reid.py
import torchreid

class ReIDExtractor:
    def __init__(self):
        self.model = torchreid.utils.FeatureExtractor(
            model_name="osnet_x1_0", model_path="osnet_x1_0_imagenet.pth", device="cpu"
        )

    def extract(self, cropped_person_img):
        return self.model(cropped_person_img)[0]  # 512-d embedding
```

```python
# fusion_server/core/reid_matcher.py
import numpy as np

SIMILARITY_THRESHOLD = 0.75

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def match_or_create_object(new_embedding, active_objects: dict) -> str:
    """active_objects: {object_id: last_embedding}. Returns matched or new object_id."""
    best_match, best_score = None, 0
    for obj_id, emb in active_objects.items():
        score = cosine_sim(new_embedding, emb)
        if score > best_score:
            best_match, best_score = obj_id, score
    if best_score >= SIMILARITY_THRESHOLD:
        return best_match
    return generate_new_object_id()
```

This is the highest-risk piece per PHASES.md — validate `SIMILARITY_THRESHOLD` empirically against your actual simulated-camera footage before moving on; don't ship the default unverified.

**Exit test:** walk from `cam1`'s frame into `cam2`'s frame and confirm `GET /footprint/{object_id}` returns both camera hops with correct timestamps and ordering.

---

## 5. Phase 3 — Ledger, Tamper Detection, Watchlist

```python
# fusion_server/core/ledger.py
import hashlib, json

def compute_hash(entry: dict, previous_hash: str) -> str:
    payload = json.dumps(entry, sort_keys=True) + (previous_hash or "")
    return hashlib.sha256(payload.encode()).hexdigest()

def append_entry(db_session, entry: dict):
    last = db_session.query(FootprintEntry).order_by(FootprintEntry.id.desc()).first()
    previous_hash = last.hash if last else ""
    entry_hash = compute_hash(entry, previous_hash)
    db_session.add(FootprintEntry(**entry, hash=entry_hash, previous_hash=previous_hash))
    db_session.commit()
    return entry_hash

def verify_chain(db_session) -> tuple[bool, int | None]:
    entries = db_session.query(FootprintEntry).order_by(FootprintEntry.id).all()
    prev_hash = ""
    for e in entries:
        expected = compute_hash({"object_id": e.object_id, "camera_id": e.camera_id,
                                   "ts": str(e.ts), "event_type": e.event_type}, prev_hash)
        if expected != e.hash:
            return False, e.id
        prev_hash = e.hash
    return True, None
```

`scripts/verify_ledger.py` runs `verify_chain` standalone — this is your tamper-detection demo script. Manually edit a row in the DB, re-run it, and it must report the exact broken entry.

```python
# edge/camera_health.py
import cv2, numpy as np

def is_tampered(frame, reference_frame) -> bool:
    if frame.mean() < 5:  # near-total darkness = covered lens
        return True
    diff = cv2.absdiff(frame, reference_frame)
    if diff.mean() < 1.0:  # frozen frame
        return True
    return False
```

**Exit test:** cover the physical/simulated camera lens — confirm a `camera_compromised` alert type fires distinct from a standard intrusion alert.

---

## 6. Phase 4 — Alerting & Intelligence

```python
# fusion_server/core/rule_engine.py
from shapely.geometry import Point, Polygon

def check_intrusion(centroid: tuple, roi_polygon: list[tuple]) -> bool:
    return Polygon(roi_polygon).contains(Point(centroid))
```

```python
# fusion_server/core/trajectory.py
from filterpy.kalman import KalmanFilter
import numpy as np

def build_tracker(initial_pos):
    kf = KalmanFilter(dim_x=4, dim_z=2)
    kf.x = np.array([initial_pos[0], initial_pos[1], 0, 0])
    kf.F = np.array([[1,0,1,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]])
    kf.H = np.array([[1,0,0,0],[0,1,0,0]])
    kf.P *= 1000
    kf.R = 5
    return kf

def project(kf, steps=5):
    projections = []
    state = kf.x.copy()
    for _ in range(steps):
        state = kf.F @ state
        projections.append((state[0], state[1]))
    return projections
```

The alert lifecycle (fire → ledger write → clip render → AI enrichment) must be implemented exactly as sequenced in ARCHITECTURE.md Section 4 — steps 3/4 as `asyncio` background tasks fired from the same handler that writes the alert, never blocking the initial response.

```python
# fusion_server/api/alerts.py (simplified)
@router.post("/internal/fire-alert")
async def fire_alert(evt: AlertFireRequest, background_tasks: BackgroundTasks):
    alert = create_alert_record(evt, status="fired")   # synchronous, fast
    append_entry(db, alert_to_footprint_entry(alert))   # synchronous ledger write
    background_tasks.add_task(render_clip_overlay, alert.alert_id)
    background_tasks.add_task(run_ai_enrichment, alert.alert_id)
    return alert
```

ANPR (`edge/detection.py` extended with a plate-detection head + `paddleocr` OCR call) is a separable module — build and test it independently against sample plate images before wiring it into the live pipeline.

**Exit test:** a tracked object crossing a configured ROI produces a visible alert on `GET /alerts` within your target latency, with `status` flipping from `fired` to `enriched` a few seconds later without the first response being delayed.

---

## 7. Phase 5 — Interfaces

- Dashboard: scaffold with `create-react-app` or Vite, consume `fusion_server` REST endpoints only (`/alerts`, `/footprint/{id}`, `/cameras/health`, `/ledger/status`). No direct DB access from the frontend, per ARCHITECTURE.md.
- Overlay rendering: use OpenCV to burn bbox + trajectory + ROI line into the saved clip at alert-fire time (`fusion_server/storage/clip_store.py`), referenced by `alerts.clip_path`.
- Blind-spot map: compute uncovered regions by taking the union of all configured ROI polygons (Shapely) against the camera's known field-of-view polygon, rendering the difference on the dashboard's camera grid.
- Patrol app: same API surface, thinner client, restrict its network calls at the OS/firewall level to LAN-only as a real enforcement, not just a convention.

---

## 8. Phase 6 — Resilience (build after core is stable)

- Coverage-gap flagging: a watchdog task that marks a camera `degraded` if no `DetectionEvent` arrives within N seconds.
- Compute-fallback: monitor per-frame inference latency; if it exceeds a threshold for M consecutive frames, hot-swap to `yolov8n` at reduced input resolution and flag `reduced_accuracy_mode=true` in the camera health record.
- Power-loss checkpointing: wrap ledger and clip writes in transactions; on restart, replay any incomplete write from a write-ahead log rather than trusting partial state.
- Offline model updates: package new weights as a signed `.tar.gz` (`gpg --detach-sign`), verify signature + SHA256 before loading — reject and alert on any mismatch.

---

## 9. Running the Full Stack (Stage 1)

```bash
# 1. Infra
docker compose up -d postgres mediamtx

# 2. Seed simulated camera streams
bash scripts/setup_simulated_cameras.sh

# 3. Fusion server
cd fusion_server && uvicorn main:app --reload --port 8000

# 4. Edge node(s) — one process per simulated camera
python edge/ingestion.py --camera rtsp://localhost:8554/cam1 --camera-id cam1
python edge/ingestion.py --camera rtsp://localhost:8554/cam2 --camera-id cam2

# 5. Dashboard
cd dashboard && npm install && npm run dev
```

## 10. Testing Standard (ties to RULES.md)

- `pytest tests/` must pass before any PR merges.
- `test_ledger_integrity.py` must include a test that deliberately corrupts an entry and asserts `verify_chain` catches it.
- `test_reid_matching.py` should run against real extracted embeddings from your simulated footage, not synthetic random vectors — a random-vector test can pass while real matching is broken.
- Manual visual QA (watching detection/tracking overlay render live) is required for Phase 1 and Phase 2 before marking them complete — automated tests alone don't satisfy the "no faking" standard in AGENTS.md.
