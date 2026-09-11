# Phase 4 — Alerting & Intelligence: Design Spec

**Date:** 2026-09-11
**Status:** FINALIZED
**Features:** #5 Virtual fence intrusion, #6 Suspicious activity, #8 Real-time alerting, #14 Threat scoring, #11 Two-speed alerting, #4 ANPR

---

## 1. Architecture Overview

Phase 4 adds an **Alert Pipeline** between the existing event ingestion and the Alert model. The pipeline has two speeds:

```
Detection Event
    │
    ├─[SYNC]─► Rule Engine ──► Alert (status: fired) ──► Hash Chain ──► SSE Broadcast
    │                          │
    │                          └─► Trajectory Projection (computed at fire time)
    │
    └─[ASYNC]─► AI Enrichment Worker ──► Alert (status: enriched)
                     │
                     └─► Natural language explanation + trajectory overlay
```

**Key invariant:** Synchronous rule checks fire the alert in <10ms. AI enrichment runs async and never blocks initial alert delivery.

### New Modules

| Module | Purpose |
|--------|---------|
| `fusion_server/core/rule_engine.py` | Already exists — wire into pipeline, add ROI DB loading |
| `fusion_server/core/trajectory.py` | Already exists — wire into alert fire path |
| `fusion_server/core/threat_scoring.py` | Already exists — wire into alert fire path |
| `fusion_server/core/suspicious_activity.py` | **New** — loitering, path reversal, group clustering |
| `fusion_server/core/anpr.py` | **New** — plate detection + OCR pipeline |
| `fusion_server/services/alert_pipeline.py` | **New** — orchestrates sync rule check + async enrichment |
| `fusion_server/services/ai_enrichment.py` | Already exists — wire with local VLM |
| `fusion_server/services/sse_broadcaster.py` | **New** — SSE alert push to connected clients |
| `fusion_server/db/models.py` | Add `ROI` table, `PlateDetection` table |
| `fusion_server/api/routes/rois.py` | **New** — ROI CRUD API |
| `fusion_server/api/routes/plates.py` | **New** — Plate detection query API |

### New DB Tables

**`roi` table:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `camera_id` | VARCHAR | FK to camera (or `*` for all cameras) |
| `name` | VARCHAR | Human-readable name (e.g., "North Perimeter Fence") |
| `polygon` | JSON | List of [x,y] normalized coordinates (0-1) |
| `alert_on_enter` | BOOLEAN | Default true |
| `alert_on_exit` | BOOLEAN | Default false |
| `object_types` | JSON | List of allowed types (e.g., `["person", "vehicle"]`) |
| `active` | BOOLEAN | Default true |
| `created_at` | TIMESTAMP | |

**`plate_detection` table:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `object_id` | VARCHAR | FK to tracked object |
| `camera_id` | VARCHAR | |
| `plate_text` | VARCHAR | OCR result (uppercase, stripped) |
| `confidence` | FLOAT | OCR confidence |
| `bbox` | JSON | Plate bounding box [x,y,w,h] |
| `created_at` | TIMESTAMP | |

---

## 2. ROI Configuration & Persistence

### API: CRUD `/api/v1/rois`

- `POST /api/v1/rois` — create ROI
- `GET /api/v1/rois` — list ROIs (filterable by camera_id)
- `GET /api/v1/rois/{roi_id}` — get one
- `PATCH /api/v1/rois/{roi_id}` — update
- `DELETE /api/v1/rois/{roi_id}` — soft delete (set active=false)

### Rule Engine Loading

On startup and on ROI CRUD, load active ROIs into the in-memory `RuleEngine` instance. The engine evaluates polygon containment against tracked object centroids.

---

## 3. Alert Pipeline (Sync + Async)

### Sync Path (fires in <10ms)

1. `POST /api/v1/events` receives detection
2. Store DetectionEvent in DB (existing)
3. Re-ID matching (existing)
4. Accumulate trajectory point in in-memory buffer (`object_id` → list of `TrajectoryPoint`)
5. Load ROIs for this camera from RuleEngine
6. Run `RuleEngine.evaluate()` — checks ROI containment, loitering, path reversal, group clustering
7. If violation found:
   a. Compute `threat_score` via `calculate_threat_score()` (existing function)
   b. Compute `trajectory_projection` via `TrajectoryProjector.predict()` (existing)
   c. Create Alert with `status: "fired"`, `reason: rule_type`, `threat_score`, `trajectory_projection`
   d. Write alert hash chain (existing `AlertLedger`)
   e. Broadcast via SSE
8. Return response (alert already fired)

### Async Path (runs in background, <5s target)

1. Background worker picks up fired alerts needing enrichment
2. Loads alert context + detection event + trajectory history
3. Calls local VLM (LLaVA-1.5-7B) to generate natural language explanation
4. Updates Alert: `status: "enriched"`, `ai_explanation: "..."`

---

## 4. Suspicious Activity Detection

Three rules, all operating on the in-memory trajectory buffer:

### Loitering (dwell time)

- Track how long an object has been inside a specific ROI
- If `dwell_time > threshold` (configurable, default 30s) → fire `loitering` alert
- Timer resets when object leaves ROI
- State: per `(object_id, roi_id)` → entry timestamp

### Path Reversal

- Track object's direction of travel (heading vector from recent positions)
- If heading changes by > 90° within a short window (configurable, default 5s) → fire `path_reversal` alert
- Indicates someone walking toward a fence, then abruptly turning back
- State: per `object_id` → last N headings

### Group Clustering

- Detect when N+ objects (configurable, default 3) are within a radius (configurable, default 5m) for > T seconds (configurable, default 10s)
- Indicates organized group activity vs. solo movement
- State: spatial index of all active object centroids

### Configuration

All thresholds stored in a `RuleConfig` dataclass with sensible defaults. Can be extended via API later but hardcoded for Phase 4.

---

## 5. Threat Scoring

The `calculate_threat_score()` function already exists in `fusion_server/core/threat_scoring.py`. It needs to be wired into the alert creation path.

### Inputs to Scoring

- `RuleViolation` list from the rule engine (type, ROI, object_type)
- `ThreatContext`:
  - `object_type`: person / vehicle
  - `time_of_day`: morning/afternoon/evening/night (configurable weights)
  - `camera_zone`: string label for the camera area
  - `previous_violations`: count of prior alerts for this object
  - `is_watchlist_match`: boolean

### Score Composition

- Base score from violation type (0.3–0.7)
- Context multipliers: night (+0.2), repeat offender (+0.1), watchlist (+0.3)
- Clamped to [0, 1]

### Threat Levels

| Score Range | Level | Action |
|-------------|-------|--------|
| 0.0–0.2 | none | Log only |
| 0.2–0.4 | low | Alert |
| 0.4–0.6 | medium | Alert + priority |
| 0.6–0.8 | high | Alert + priority + clip |
| 0.8–1.0 | critical | Alert + priority + clip + immediate AI enrichment |

### Wiring

Replace all hardcoded `threat_score` values (0.9 for watchlist, 0.8 for camera compromise) with calls to `calculate_threat_score()`.

---

## 6. SSE Real-Time Alert Push

### Endpoint

`GET /api/v1/alerts/stream`

### Behavior

- Client connects, receives `text/event-stream` response
- On each fired or enriched alert, server pushes an event:
  ```
  event: alert_fired
  data: {"alert_id": "...", "camera_id": "...", "reason": "...", "threat_score": 0.7, "timestamp": "..."}

  event: alert_enriched
  data: {"alert_id": "...", "ai_explanation": "...", "trajectory_projection": [...]}
  ```
- Connection stays open until client disconnects
- Multiple clients supported (broadcast pattern)

### Implementation

Simple in-memory set of `asyncio.Queue` per connected client. No external dependencies (no Redis, no WebSocket library).

### Viewer

A minimal HTML page at `/viewer` that connects to the SSE endpoint and displays alerts in a list with color-coded threat levels.

---

## 7. ANPR Pipeline

### Separate Workstream

ANPR runs as a parallel worker, independent of the main alert pipeline.

### Pipeline

1. Detection event with `object_type: "vehicle"` arrives
2. Crop vehicle bbox from frame
3. Run plate detection model (pre-trained YOLOv8 fine-tuned on plate datasets)
4. If plate detected: crop plate region
5. Run OCR (PaddleOCR or EasyOCR) on plate crop
6. Store result: `PlateDetection` model with `plate_text`, `confidence`, `camera_id`, `timestamp`, `object_id`
7. If plate matches watchlist (`watchlist_type: "plate"`) → fire `plate_watchlist_match` alert

### API

`GET /api/v1/plates` — query plate detections (filterable by camera, time range, plate text)

### Integration

ANPR runs as a parallel worker. It consumes the same detection events but only processes vehicles. Results feed into the watchlist matcher for plate-type entries.

---

## 8. Trajectory Projection at Alert Time

### Current State

`trajectory_projection` on Alert is always `None`. Nothing populates it.

### Design

When an alert fires, the rule engine has access to the in-memory trajectory buffer for the triggering object. At alert-fire time:

1. Extract last N points (default 20) from trajectory buffer
2. Feed to `TrajectoryProjector` (existing class in `fusion_server/core/trajectory.py`)
3. `predict(steps=10)` returns 10 future positions
4. Store both the history and prediction on the Alert:
   ```json
   "trajectory_projection": {
     "history": [[x1,y1], [x2,y2], ...],
     "predicted": [[px1,py1], [px2,py2], ...],
     "confidence": 0.85
   }
   ```

### Reconstruction

If trajectory buffer is lost (restart), reconstruct from recent DetectionEvent history in the DB (query last 20 events for this object_id).

### Overlay

The viewer renders the trajectory as a colored line (green=history, yellow=predicted) on the video frame.

---

## 9. Data Contracts (ARCHITECTURE.md Section 5 Updates)

### ROI (new)

```json
{
  "id": "UUID",
  "camera_id": "string (or '*' for all)",
  "name": "string",
  "polygon": [[x, y], ...],
  "alert_on_enter": true,
  "alert_on_exit": false,
  "object_types": ["person", "vehicle"],
  "active": true
}
```

### Alert (updated fields)

```json
{
  "alert_id": "string",
  "object_id": "string",
  "camera_id": "string",
  "timestamp": "ISO8601",
  "reason": "string (roi_intrusion | loitering | path_reversal | group_clustering | watchlist_match | plate_watchlist_match | camera_compromised)",
  "status": "fired | enriched | acknowledged",
  "threat_score": "float (0-1)",
  "clip_path": "string | null",
  "ai_explanation": "string | null",
  "trajectory_projection": {
    "history": [[x, y], ...],
    "predicted": [[x, y], ...],
    "confidence": "float"
  } | null,
  "hash": "string",
  "previous_hash": "string | null"
}
```

### PlateDetection (new)

```json
{
  "id": "UUID",
  "object_id": "string",
  "camera_id": "string",
  "plate_text": "string",
  "confidence": "float",
  "bbox": [x, y, w, h],
  "timestamp": "ISO8601"
}
```

---

## 10. Exit Criteria

**Live demo — all must work on real/simulated input:**

1. A tracked object crossing a configured ROI fires an alert within acceptable latency (<10ms rule check)
2. The alert appears immediately on the basic viewer via SSE
3. The alert is enriched with an AI explanation + trajectory overlay within a few seconds
4. The initial alert is NOT delayed by the AI enrichment
5. Threat score is computed deterministically (not hardcoded)
6. Trajectory projection is populated on the alert at fire time

---

## 11. Constraints

- Deterministic-only for alert decisions (no ML in the rule engine path)
- `threat_score` field has CHECK constraint `0 <= score <= 1`
- Data contracts in ARCHITECTURE.md Section 5 are frozen — no field changes without updating the doc
- AI enrichment must never block alert delivery (async only)
- Ledger write is synchronous and blocking
- No external API calls for core functionality — local models only
- All features must work on real input, no faked/stubbed paths without `[SIMULATED / UNIT-TESTED ONLY]` marker
- ANPR can be a separate person working in parallel

---

## 12. Deferred (Documented, Not Built This Cycle)

- **#13 Cross-BOP federation:** Design the sync protocol, demo on two LAN nodes simulating adjacent BOPs. Do not claim field-tested multi-BOP validation.
- **#18 Multi-modal sensor fusion:** Documented as an extension point in ARCHITECTURE.md only. No stub implementation, since there is no real sensor input to validate against.
