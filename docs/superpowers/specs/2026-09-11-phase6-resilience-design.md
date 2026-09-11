# Phase 6 — Resilience Hardening: Design Spec

**Date:** 2026-09-11
**Status:** Approved — ready for implementation planning
**Depends on:** Phases 0–5 (all complete)

---

## 1. Goal

Make the IBVAP system visibly degrade instead of silently failing. When a camera goes down, compute overloads, power drops, or a crash occurs mid-write, the system must produce a visible state change — never a silent gap.

**Scope:** All 5 Phase 6 features from PHASES.md:
- Coverage-gap flagging on camera disconnect
- Automatic fallback to a lighter model under compute load
- Checkpoint/resume logic for the ledger and in-progress clips
- Low-power fallback mode
- Signed model package format + hash verification

**Validation:** All features validated in simulation only. Real edge/power hardware testing is Stage 3 (documented in ARCHITECTURE.md).

---

## 2. Architecture

Event-driven resilience bus. Each concern is an independent monitor that publishes health events. A `ResilienceAggregator` collects all signals and pushes unified status to the dashboard via SSE.

```
┌──────────────────────────────────────────────────────┐
│                   Edge Node                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐      │
│  │ Camera   │  │Detection │  │  Model       │      │
│  │ Worker   │  │ Service  │  │  Verifier    │      │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘      │
│       │ heartbeat    │ metrics       │ verify        │
│       ▼              ▼               ▼               │
│  ┌──────────────────────────────────────────────┐   │
│  │          Resilience Bus (asyncio)             │   │
│  └──────────────────────┬───────────────────────┘   │
└─────────────────────────┼────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────┼────────────────────────────┐
│  Fusion Server          │                            │
│  ┌──────────────────────▼───────────────────────┐   │
│  │           Resilience Monitors                 │   │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │   │
│  │  │Camera   │ │Detector  │ │Ledger        │  │   │
│  │  │Offline  │ │Fallback  │ │Checkpoint    │  │   │
│  │  │Monitor  │ │Monitor   │ │Writer        │  │   │
│  │  └─────────┘ └──────────┘ └──────────────┘  │   │
│  │  ┌──────────┐                                │   │
│  │  │Power    │                                │   │
│  │  │Manager  │                                │   │
│  │  └─────────┘                                │   │
│  └──────────────────────┬───────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼───────────────────────┐   │
│  │        ResilienceAggregator                   │   │
│  │  - Computes system health score               │   │
│  │  - Pushes SSE events to dashboard             │   │
│  │  - Logs to ledger for audit                   │   │
│  └──────────────────────┬───────────────────────┘   │
└─────────────────────────┼────────────────────────────┘
                          │ SSE
┌─────────────────────────┼────────────────────────────┐
│  Dashboard              ▼                            │
│  ┌──────────────────────────────────────────────┐   │
│  │  Header: health badge + expandable detail     │   │
│  │  Cameras: status badges + coverage gaps       │   │
│  │  Detection: tier indicator                    │   │
│  │  Ledger: chain health                         │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

## 3. Feature Designs

### 3.1 Camera Offline Detection + Coverage Gap Flagging

**Current state:** Edge workers POST health every N frames (frame-count-based). `CameraHealthStore` is an in-memory dict with no staleness check. A dead worker is never detected.

**Changes:**

**Edge side (`edge/camera_worker.py`):**
- Change health heartbeat from frame-count-based to time-based (default: 30s)
- POST to `POST /api/v1/cameras/{camera_id}/heartbeat` with timestamp

**Server side — new file `fusion_server/services/camera_offline_monitor.py`:**
- `CameraOfflineMonitor` class:
  - `start()` — launches background `asyncio.Task` that runs every 10s
  - `_check_staleness()`:
    - For each camera in `CameraHealthStore`:
      - If `last_seen` > 2× heartbeat_interval (60s) → status = `"offline"`
      - If `last_seen` > 5× heartbeat_interval (150s) → status = `"stale"`
    - On first offline detection: fires alert via `AlertLedger`
    - Suppresses repeated offline alerts for 60s per camera
  - `stop()` — cancels the background task

**Server side — `fusion_server/services/camera_health_store.py`:**
- Add `last_seen: datetime` field per camera
- Add `heartbeat(camera_id)` method that updates `last_seen`
- Add `is_stale(camera_id, threshold_seconds)` method

**Server side — `fusion_server/services/resilience_aggregator.py`:**
- When camera goes offline:
  - Compute coverage gaps: find cameras whose ROI overlaps the offline camera's ROI (using existing `coverage.py` Shapely logic)
  - Mark overlapping zones as `"coverage_gap"` with percentage of area affected
  - Push `camera_status_changed` SSE event

**API — `fusion_server/api/routes/cameras.py`:**
- New endpoint: `POST /api/v1/cameras/{camera_id}/heartbeat` — updates `last_seen`
- Existing `GET /api/v1/cameras/health` — now includes `status` (online/offline/stale/unknown) and `last_seen`

**Dashboard — `dashboard/src/components/CameraGrid.tsx`:**
- Camera feed badges: green (online), yellow (degraded), red (offline), gray (unknown)
- Coverage gap overlay on the map component

**SSE event:** `camera_status_changed`
```json
{
  "camera_id": "cam1",
  "status": "offline",
  "coverage_gaps": [{"zone": "parking_lot", "area_pct": 35}]
}
```

---

### 3.2 Two-Tier Model Fallback

**Current state:** `DetectionService` is hardcoded to `yolov8n.pt`. No fallback if inference is slow or failing.

**Changes:**

**New file `fusion_server/services/detector_fallback.py`:**
- `DetectorFallback` class:
  - Tracks: inference latency (rolling 60s avg), queue depth, error rate
  - Thresholds:
    - **Tier 1 (degraded):** latency > 200ms avg OR queue > 10 → load `yolov8n.pt` (if not already) or `yolov8n-nano.pt` if available
    - **Tier 2 (critical):** latency > 500ms avg OR queue > 30 OR error rate > 10% → motion-only detection
    - **Recovery:** metrics normal for 30s → step back up
  - Emits `detection_tier_changed` event

**Edge side — `edge/detector.py`:**
- Add `set_model(path: str)` method: loads new YOLO weights, swaps reference
- Add `_run_motion_detection(frame)` method: frame-difference based, returns bounding boxes of moving regions
- `_run_inference` dispatches to YOLO or motion detection based on current tier

**Edge side — `edge/camera_worker.py`:**
- Reports inference latency per frame to `DetectorFallback` via shared queue
- `DetectorFallback` adjusts tier and notifies all workers

**Dashboard — `dashboard/src/components/Header.tsx`:**
- Detection tier badge: "Detection: Normal" / "Detection: Degaded (nano)" / "Detection: Critical (motion-only)"

**SSE event:** `detection_tier_changed`
```json
{
  "from": "normal",
  "to": "degraded",
  "reason": "latency_250ms_avg",
  "model": "yolov8n-nano.pt"
}
```

---

### 3.3 Checkpoint/Resume for Ledger + Clips

**Current state:** No checkpoint mechanism. A crash mid-write leaves the hash chain potentially incomplete. In-progress clip files are orphaned.

**Changes:**

**New file `fusion_server/services/ledger_checkpoint.py`:**
- `LedgerCheckpoint` class:
  - `write_checkpoint(alert_id, hash, chain_length)` — writes JSON to `data/checkpoints/ledger_<timestamp>.json`
  - `resume()` — reads latest checkpoint, verifies chain from that point, logs gaps
  - `get_status()` — returns `{"status": "ok"|"gap_detected", "last_verified": ..., "chain_length": ...}`
  - Rolling window: keeps last 10 checkpoints, deletes older ones

**Checkpoint file format:**
```json
{
  "last_alert_id": 42,
  "last_hash": "abc123...",
  "chain_length": 156,
  "timestamp": "2026-09-11T15:30:00Z"
}
```

**Integration — `fusion_server/core/alert_ledger.py`:**
- After `write_alert_with_hash` succeeds, call `LedgerCheckpoint.write_checkpoint()`
- On startup, call `LedgerCheckpoint.resume()`

**New file `fusion_server/services/clip_checkpoint.py`:**
- `ClipCheckpoint` class:
  - `mark_pending(alert_id)` — writes `.pending` marker file
  - `mark_complete(alert_id)` — deletes `.pending` file
  - `scan_orphans()` — finds `.pending` files with no active rendering, logs warning
  - Returns list of `"incomplete"` clips for dashboard display

**Integration — `fusion_server/api/alerts.py`:**
- Before clip overlay starts: `ClipCheckpoint.mark_pending(alert_id)`
- After overlay completes: `ClipCheckpoint.mark_complete(alert_id)`
- On startup: `ClipCheckpoint.scan_orphans()`

**Dashboard:**
- Ledger status: "Ledger: OK (156 entries)" or "Ledger: Gap detected at entry #42"
- Incomplete clips shown with warning badge in event log

**SSE events:** `ledger_resumed`, `clip_recovery`

---

### 3.4 Low-Power Fallback Mode

**Current state:** No power management. System runs at full capacity regardless of resource constraints.

**Changes:**

**New file `fusion_server/services/power_manager.py`:**
- `PowerManager` class:
  - Monitors CPU usage and available memory via `psutil` (with fallback to `/proc/stat` on Linux)
  - Three modes:
    - **Normal:** all cameras active, full FPS (10), full detection+tracking+ReID
    - **Reduced:** CPU > 80% OR memory < 20% free → drop lowest-priority cameras, FPS 10→2, disable ReID
    - **Critical:** CPU > 95% OR memory < 10% free → single camera only, FPS=1, detection only (no tracking, no ReID, no overlay)
  - Mode transitions: publish `power_mode_changed` SSE event
  - Recovery: load below threshold for 60s → step back up
  - Camera priority: configurable per-camera (default: by ROI area — larger ROI = higher priority)

**Dashboard — `dashboard/src/components/Header.tsx`:**
- Power mode badge: "Power: Normal" / "Power: Reduced" / "Power: Critical"

**SSE event:** `power_mode_changed`
```json
{
  "from": "normal",
  "to": "reduced",
  "reason": "cpu_85%",
  "affected_cameras": ["cam3", "cam4"]
}
```

---

### 3.5 Signed Model Packages + Hash Verification

**Current state:** No model authenticity verification. Model files are loaded directly with no integrity check.

**Changes:**

**Package format (`.pt.signed`):**
- ZIP archive containing:
  - `model.pt` — YOLO weights file
  - `metadata.json` — model name, version, SHA-256 hash of model.pt, creation timestamp
  - `signature.bin` — Ed25519 signature of `metadata.json` content

**New script `scripts/generate_model_keys.py`:**
- Generates Ed25519 keypair using `cryptography` library
- Saves `model_signing.key` (private) and `model_signing.pub` (public) to `config/model_keys/`
- Private key stays on signing machine; public key deployed to edge

**New script `scripts/sign_model.py`:**
- Takes unsigned `.pt` file + private key → produces `.pt.signed` package
- Computes SHA-256 of model, creates metadata.json, signs with Ed25519

**New file `edge/model_verifier.py`:**
- `ModelVerifier` class:
  - `verify(signed_path: str, public_key_path: str) -> bool`:
    1. Extract ZIP
    2. Read `metadata.json` and `signature.bin`
    3. Verify Ed25519 signature against public key
    4. Verify SHA-256 hash of `model.pt` matches metadata hash
    5. Return True/False
  - `load_verified_model(signed_path, public_key_path)` — verify + load into DetectionService
  - All verification attempts logged to ledger as `model_verification` event type

**Integration with DetectorFallback:**
- If primary model fails to load or is corrupted → automatic fallback to tier 1/tier 2
- Model verification failure → alert + reject, do not load

---

### 3.6 Unified Degraded Mode Status

**New file `fusion_server/services/resilience_aggregator.py`:**
- `ResilienceAggregator` class:
  - Subscribes to events from all monitors
  - Computes system health score:
    - `"ok"` — all subsystems nominal
    - `"degraded"` — any subsystem in degraded state (camera offline, detection tier 1, power reduced)
    - `"critical"` — any subsystem in critical state (multiple cameras offline, detection tier 2, power critical, ledger gap)
  - Pushes `system_health_changed` SSE event on any status change

**New API — `fusion_server/api/routes/system.py`:**
- `GET /api/v1/system/health`:
```json
{
  "status": "degraded",
  "cameras": {"cam1": "online", "cam2": "offline"},
  "coverage_gaps": [{"zone": "parking_lot", "area_pct": 35}],
  "detection_tier": "nano",
  "ledger": {"status": "ok", "entries": 156},
  "power_mode": "normal"
}
```

**Dashboard — `dashboard/src/components/Header.tsx`:**
- Health badge: green/yellow/red
- Expandable detail panel with subsystem statuses
- Clickable → navigates to relevant view

---

## 4. New Files Summary

| File | Purpose |
|------|---------|
| `fusion_server/services/camera_offline_monitor.py` | Heartbeat timeout + offline detection |
| `fusion_server/services/detector_fallback.py` | Model tier switching based on load |
| `fusion_server/services/ledger_checkpoint.py` | File-based checkpoint for ledger chain |
| `fusion_server/services/clip_checkpoint.py` | Pending/complete markers for clips |
| `fusion_server/services/power_manager.py` | CPU/memory monitoring + power modes |
| `fusion_server/services/model_verifier.py` | Ed25519 signature + hash verification |
| `fusion_server/services/resilience_aggregator.py` | Unified health score + SSE push |
| `fusion_server/api/routes/system.py` | `GET /api/v1/system/health` |
| `scripts/generate_model_keys.py` | Ed25519 keypair generation |
| `scripts/sign_model.py` | Model signing tool |
| `edge/model_verifier.py` | Edge-side model verification |
| `dashboard/src/components/SystemHealth.tsx` | Health badge + detail panel |
| `tests/test_camera_offline_monitor.py` | Offline monitor tests |
| `tests/test_detector_fallback.py` | Fallback logic tests |
| `tests/test_ledger_checkpoint.py` | Checkpoint write/resume tests |
| `tests/test_clip_checkpoint.py` | Clip checkpoint tests |
| `tests/test_power_manager.py` | Power manager tests |
| `tests/test_model_verifier.py` | Signature verification tests |
| `tests/test_resilience_integration.py` | End-to-end resilience tests |

---

## 5. Data Contract Updates

New event types for the ledger:
- `camera_offline` — camera lost heartbeat
- `coverage_gap` — zone coverage dropped below threshold
- `detection_tier_changed` — model fallback activated
- `ledger_resumed` — server recovered from checkpoint
- `clip_recovery` — orphaned clip detected
- `power_mode_changed` — power mode transition
- `model_verification` — model signature verified/rejected

New SSE event types:
- `camera_status_changed`
- `detection_tier_changed`
- `power_mode_changed`
- `system_health_changed`
- `ledger_resumed`
- `clip_recovery`

---

## 6. AGENTS.md Compliance

- **Rule 1 (No ML alert decisions):** Resilience monitors flag degraded state but do not make detection/tracking decisions. Model fallback changes the inference engine, not the alert logic.
- **Rule 2 (No raw video across boundaries):** Checkpoint files contain metadata only, not video frames. Clip checkpoints are marker files, not video data.
- **Rule 3 (Sync ledger writes):** Ledger checkpoint writes are synchronous (same as alert ledger). Checkpoint is written after successful ledger write, before returning.
- **Rule 4 (AI enrichment never blocks delivery):** Model fallback is a pre-inference optimization, not post-detection enrichment. It does not block alert delivery.
- **Rule 5 (Data contracts frozen):** New event types are additions, not modifications to existing contracts. Existing fields unchanged.

---

## 7. Testing Strategy

**Unit tests (per monitor):**
- Camera offline monitor: heartbeat timeout, staleness detection, alert suppression
- Detector fallback: tier switching, recovery, motion-only fallback
- Ledger checkpoint: write, resume, gap detection, rolling window
- Clip checkpoint: pending/complete lifecycle, orphan detection
- Power manager: mode transitions, camera priority, recovery
- Model verifier: valid signature, invalid signature, corrupted model, hash mismatch

**Integration tests:**
- Simulated camera disconnect → offline detection → coverage gap → SSE event → dashboard update
- Simulated CPU spike → model fallback → tier change → SSE event → dashboard indicator
- Simulated crash mid-ledger-write → restart → checkpoint resume → chain integrity
- Simulated power drop → mode reduction → camera deactivation → recovery

**Exit criteria (simulation only):**
- Kill a camera feed → system flags offline + coverage gap within 60s
- Throttle CPU → model falls back to tier 1 then tier 2
- Kill server mid-write → restart recovers from checkpoint
- All tests pass; no silent failures

---

## 8. Deferred (Noted, Not Built)

- **Cross-BOP federation** (#13) — sync protocol design only, no implementation
- **Multi-modal sensor fusion** (#18) — extension point in ARCHITECTURE.md only
- **Real hardware power testing** — Stage 3 per ARCHITECTURE.md
- **GPU memory monitoring** — requires nvidia-smi integration, deferred to Stage 3
- **Battery/UPS status** — documented as extension point in PowerManager

---

*Spec approved — ready for implementation planning.*
