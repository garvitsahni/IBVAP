# Phase 2 — Cross-Camera Identity Design Spec

> **Date:** 2026-09-11
> **Status:** Approved
> **Owner:** 1–2 engineers (ML-experienced)

## 1. Goal

Build cross-camera person/vehicle re-identification, footprint chain tracking, and camera health monitoring. Exit criteria: walk from one camera's FOV into another's, see the footprint chain update in real time, correctly identifying it as the same object across both cameras.

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    EDGE NODE                              │
│                                                           │
│  [CameraWorker] ──► DetectionService (YOLOv8n)            │
│       │                    │                              │
│       │              detections + bbox                    │
│       │                    │                              │
│       │         ┌──────────▼──────────┐                  │
│       │         │  ReIDService        │                  │
│       │         │  (OSNet / Vehicle)  │                  │
│       │         │  crops bbox from    │                  │
│       │         │  frame, extracts    │                  │
│       │         │  512-dim embedding  │                  │
│       │         └──────────┬──────────┘                  │
│       │                    │                              │
│       │    DetectionEvent + embedding[]                   │
│       │                    │                              │
│       ▼                    ▼                              │
│  ┌─────────────────────────────────────┐                 │
│  │  EventPublisher                      │                 │
│  │  POST /api/v1/events                 │                 │
│  └─────────────────────────────────────┘                 │
│                                                           │
│  [CameraHealthService] ──► frame-diff + SSIM             │
│       │                    reference frame store          │
│       │                                                   │
└───────┼───────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                 FUSION SERVER                              │
│                                                           │
│  POST /api/v1/events                                      │
│       │                                                   │
│       ├──► MatchingEngine (pgvector cosine search)        │
│       │         │                                         │
│       │    best_match.object_id (or new)                  │
│       │         │                                         │
│       ├──► FootprintChainWriter                           │
│       │         │                                         │
│       │    first_seen / hop / last_seen                   │
│       │         │                                         │
│       └──► CameraHealthStore                              │
│                  │                                        │
│             drift alerts                                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## 3. Edge-Side Re-ID Service

### 3.1 ReIDService

Runs as a separate process (like DetectionService). Receives crops from CameraWorker via `multiprocessing.Queue`, returns 512-dim embeddings.

**Models:**
- **Person Re-ID:** OSNet (onnx-reid, ~10MB, 512-dim embeddings). Runs on CPU.
- **Vehicle Re-ID:** Lightweight CNN model (~5MB, 512-dim embeddings). Runs on CPU.

**Pipeline:**
1. CameraWorker gets detections from DetectionService
2. For each detection, crop the bounding box from the frame
3. Send `(frame_id, camera_id, crop_image, object_type)` to ReIDService via Queue
4. ReIDService resizes crop to 256x128, runs inference, returns 512-dim embedding
5. CameraWorker attaches embedding to DetectionEvent before publishing

**Fallback:** If Re-ID model fails to load, embedding stays `null` — system degrades gracefully (no cross-camera matching, but detections still work).

### 3.2 Model Loading

- OSNet loaded from `models/osnet_ain_x1_0.onnx` (ONNX format for CPU inference)
- Vehicle model loaded from `models/vehicle_reid.onnx`
- Both models use `onnxruntime` for inference (lightweight, no GPU required)

## 4. Fusion Server — Matching Engine

### 4.1 Async Matching

When a DetectionEvent arrives with an embedding:
1. Event is stored immediately in `detection_events` table (with `embedding` column)
2. Background worker picks up the event
3. Queries `pgvector` for top-K nearest embeddings of same `object_type` within time window (last 5 minutes)
4. Computes cosine similarity between new embedding and candidates
5. If best match > threshold → assign existing `object_id`
6. If no match → create new `object_id` (UUID)
7. Updates `detection_events` row with assigned `object_id`

### 4.2 Thresholds

- Person Re-ID: 0.65 (OSNet is well-calibrated)
- Vehicle Re-ID: 0.60 (lightweight model, more lenient)

### 4.3 Time Window

Only search embeddings from the last N minutes (configurable, default 5 minutes). Prevents matching against stale data and keeps the index fast.

### 4.4 Index

pgvector `ivfflat` index on the `embedding` column, filtered by `object_type` and `timestamp`.

## 5. Footprint Chain Writer

### 5.1 Logic

When the matching engine assigns an `object_id` to a DetectionEvent:

1. **Check if object exists** — query `footprint_entries` for this `object_id`
2. **If first time seen:**
   - Write `first_seen` entry with `camera_id`, `timestamp`, `hash`
3. **If already seen:**
   - Check last entry's `camera_id`
   - If same camera → no new hop (skip, or write `hop` if >30s gap)
   - If different camera → write `hop` entry
4. **On last-seen** (track disappears for >60 frames):
   - Write `last_seen` entry

### 5.2 Hash Chain

Each entry includes:
```
hash = SHA256(object_id + camera_id + timestamp + event_type + previous_hash)
```

This is the tamper-evident ledger from Phase 3 — we write the chain now, verify it later.

### 5.3 API Endpoint

`GET /api/v1/footprint/{object_id}` returns the full chain:
```json
{
  "object_id": "abc-123",
  "object_type": "person",
  "hops": [
    {"camera_id": "cam1", "event_type": "first_seen", "timestamp": "..."},
    {"camera_id": "cam2", "event_type": "hop", "timestamp": "..."},
    {"camera_id": "cam3", "event_type": "hop", "timestamp": "..."}
  ]
}
```

## 6. Camera Drift Detection

### 6.1 Layer 1 — Frame-level (tamper/movement)

- Store a reference frame per camera (captured at startup or manually calibrated)
- Every 30 seconds, compute SSIM between live frame and reference
- If SSIM < 0.3 → camera moved/tampered → fire `camera_drift` alert
- If SSIM < 0.1 → lens covered/blinded → fire `camera_tamper` alert

### 6.2 Layer 2 — Embedding-level (scene change)

- Store a "scene embedding" per camera (average of last 100 person/vehicle embeddings)
- When new embedding arrives, compare to scene embedding
- If cosine similarity drops significantly → scene changed (new background objects, lighting shift)
- Less urgent than tamper, more about monitoring degradation

### 6.3 Storage

- Reference frames: stored in MinIO (or local filesystem for Stage 1)
- Scene embeddings: stored in a simple in-memory dict per camera (rebuilt from DB on startup)

### 6.4 API Endpoint

`GET /api/v1/cameras/health` returns:
```json
{
  "cam1": {"status": "ok", "ssim": 0.87, "scene_drift": false},
  "cam2": {"status": "tamper", "ssim": 0.05, "scene_drift": false}
}
```

## 7. Live Demo Setup

### 7.1 Scenario

Walk from Camera 1's FOV into Camera 2's FOV.

### 7.2 Setup

1. Two RTSP feeds via mediamtx — one looped video per camera (different angles of same area)
2. DetectionService + ReIDService running as processes
3. Two CameraWorkers — one per camera, each with its own MJPEG stream
4. Fusion server receiving events, matching, building footprint chain

### 7.3 Demo Flow

1. Person appears in Camera 1 → `first_seen` entry written
2. Person moves to Camera 2 → `hop` entry written, same `object_id`
3. Open `http://localhost:8000/api/v1/footprint/{object_id}` → see chain with both cameras
4. Cover Camera 2 lens → `camera_tamper` alert fires

### 7.4 API Endpoints

- `POST /api/v1/events` — receives DetectionEvents (already exists)
- `GET /api/v1/footprint/{object_id}` — returns footprint chain (new)
- `GET /api/v1/cameras/health` — returns camera health status (new)
- `GET /api/v1/events` — list recent events (already exists)

## 8. New Files

```
edge/
├── reid_service.py              # ReIDService: OSNet + vehicle ReID inference
├── camera_health.py             # CameraHealthService: SSIM + scene embedding

fusion_server/
├── api/routes/footprint.py      # GET /api/v1/footprint/{object_id}
├── api/routes/cameras.py        # GET /api/v1/cameras/health
├── services/
│   ├── matching_engine.py       # pgvector cosine search + object_id assignment
│   ├── footprint_writer.py      # Footprint chain logic
│   └── camera_health_store.py   # Reference frames + scene embeddings

tests/
├── test_reid_service.py         # ReIDService unit tests
├── test_matching_engine.py      # Matching engine tests
├── test_footprint_writer.py     # Footprint chain tests
├── test_camera_health.py        # Camera drift detection tests
└── test_integration_phase2.py   # Full pipeline integration test

models/
├── osnet_ain_x1_0.onnx          # Person Re-ID model (download)
└── vehicle_reid.onnx             # Vehicle Re-ID model (download)
```

## 9. Dependencies

Add to `requirements.txt`:
```
onnxruntime>=1.17.0
scikit-image>=0.22.0   # for SSIM
```

## 10. Testing Strategy

- **Unit tests:** ReIDService (mock model), matching engine (mock pgvector), footprint writer (mock DB)
- **Integration test:** Full pipeline with synthetic data — detections → embeddings → matching → footprint chain
- **Live demo:** Two RTSP feeds, walk between cameras, verify footprint chain via API

## 11. Non-Goals (Stage 1)

- Real-time dashboard visualization (Phase 5)
- Multi-BOP federation (deferred)
- Watchlist matching (Phase 3)
- Alert rule engine (Phase 4)
