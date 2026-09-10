# IBVAP — Technical Architecture

## 1. Architecture Principles

1. **Deterministic engines own high-stakes verdicts.** Any decision that triggers an alert (intrusion, tamper, fence crossing) is made by explicit geometry/rule logic — never by an LLM, and never by a black-box confidence score alone.
2. **LLMs handle extraction, summarization, and explanation only** — they enrich an alert after it fires, they never decide whether it fires.
3. **Nothing leaves the BOP.** No architecture decision may introduce a hard dependency on external network access for core functionality.
4. **Every stage writes evidence, not just output.** Detections, footprint hops, and alerts are persisted with enough context to be replayed and audited later — this is what makes the ledger meaningful.
5. **Graceful degradation over silent failure.** A camera going down, compute overload, or power loss must produce a visible system state change, never a silent gap.

## 2. System Topology

```
┌─────────────────────────────────────────────────────────┐
│                      BOP PERIMETER                        │
│                                                             │
│  [Camera 1]   [Camera 2]   [Camera 3]   ...                │
│      │             │             │                         │
│      ▼             ▼             ▼                         │
│  ┌─────────────────────────────────────────┐               │
│  │           EDGE PROCESSING NODE(S)         │               │
│  │  - RTSP ingestion                         │               │
│  │  - Detection (YOLOv8n)                    │               │
│  │  - Single-camera tracking (ByteTrack)     │               │
│  │  - Re-ID embedding extraction             │               │
│  │  - Camera health / tamper checks          │               │
│  └───────────────────┬───────────────────────┘               │
│                       │  (structured events, embeddings,     │
│                       │   short clips only — no raw stream)  │
│                       ▼                                       │
│  ┌─────────────────────────────────────────┐               │
│  │           BOP FUSION SERVER               │               │
│  │  - Cross-camera re-ID matching            │               │
│  │  - Footprint chain builder                │               │
│  │  - Virtual fence / rule engine            │               │
│  │  - Threat scoring                         │               │
│  │  - Hash-chain ledger                      │               │
│  │  - Local watchlist matching               │               │
│  │  - AI enrichment (async, non-blocking)    │               │
│  │  - PostgreSQL + local object store        │               │
│  │  - FastAPI backend                        │               │
│  └───────────────────┬───────────────────────┘               │
│                       │  (LAN only)                           │
│           ┌───────────┴───────────┐                          │
│           ▼                       ▼                          │
│    [Command Dashboard]     [Patrol Companion App]             │
│                                                             │
└─────────────────────────────────────────────────────────┘
             │ (optional, one-way, deliberate)
             ▼
      [HQ — alert summaries only, never required for operation]
```

## 3. Component Breakdown

### 3.1 Edge Processing Node
- **Input:** RTSP stream per camera (real cameras or simulated via `mediamtx` + looped footage during development).
- **Detection:** YOLOv8n — chosen for CPU-viability during laptop-stage development, upgradeable to larger weights on real edge GPU hardware later.
- **Tracking:** ByteTrack, per-camera track IDs.
- **Re-ID embedding:** OSNet (person), vehicle-ReID model — computed once per detection, attached to the event object.
- **Night/weather adaptation:** brightness and visibility estimators branch the pipeline into alternate preprocessing/model weights before detection.
- **Camera health:** frame-diff heuristics run continuously, independent of the detection pipeline, to catch tamper/blinding/drift.
- **Output contract:** see Section 5 (Data Contracts) — a structured event object, never raw video, sent to the Fusion Server.

### 3.2 BOP Fusion Server
- **Re-ID matching engine:** cosine similarity search over a rolling embedding index; matches above threshold are linked into the same footprint chain.
- **Footprint ledger:** append-only table of `(object_id, camera_id, timestamp, event_type, hash, previous_hash)`.
- **Rule engine:** polygon ROI vs. tracked centroid — pure geometry, evaluated every frame, fires instantly on violation.
- **Threat scoring:** a scoring function combining time-of-day weight, historical ROI incident frequency, and trajectory confidence — deterministic and inspectable, not a black box.
- **AI enrichment service:** subscribes to the alert stream asynchronously; never blocks alert delivery; writes its output as an addendum to the existing alert record, not a replacement.
- **Watchlist matcher:** local encrypted embedding store, compared against face/plate embeddings at detection time.
- **Storage:** PostgreSQL for structured data (alerts, footprint, watchlist metadata), local object store (filesystem or MinIO) for clips and reference frames.

### 3.3 Interfaces
- **Command dashboard:** FastAPI-served or React frontend, reads from the Fusion Server's API only — no direct DB access from the frontend.
- **Patrol companion app:** same API surface as the dashboard, thinner client, LAN-only, no external network calls permitted at all.

## 4. Alert Lifecycle (Two-Speed Design)

1. Rule engine detects a violation → alert record created with `status: fired`, deterministic reason string, timestamp, camera ID, object ID — **written and broadcast immediately**.
2. Ledger writer hashes the new alert against the previous chain entry — synchronous, fast, blocking (this must never be skipped).
3. Clip renderer burns bounding box + trajectory + ROI line into the saved clip — async, does not block the alert being visible on the dashboard.
4. AI enrichment service picks up the alert asynchronously, generates a natural-language explanation and trajectory projection, appends it to the alert record as `status: enriched` — dashboard updates in place when this arrives.

No step in 3 or 4 may delay step 1 reaching the dashboard/patrol app.

## 5. Data Contracts (Frozen at Phase 0)

### DetectionEvent (edge → fusion server)
```json
{
  "camera_id": "string",
  "timestamp": "ISO8601",
  "object_type": "person | vehicle",
  "track_id": "string",
  "bbox": [x, y, w, h],
  "embedding": [float, ...],
  "confidence": float
}
```

### FootprintEntry (fusion server, ledger)
```json
{
  "object_id": "string",
  "camera_id": "string",
  "timestamp": "ISO8601",
  "event_type": "first_seen | hop | alert | last_seen",
  "hash": "string",
  "previous_hash": "string"
}
```

### Alert (fusion server → interfaces)
```json
{
  "alert_id": "string",
  "object_id": "string",
  "camera_id": "string",
  "timestamp": "ISO8601",
  "reason": "string",
  "status": "fired | enriched",
  "threat_score": float,
  "clip_path": "string | null",
  "ai_explanation": "string | null",
  "trajectory_projection": [[x, y], ...] | null
}
```

These three contracts are the seams between every team member's workstream. Changing any field requires updating this document and notifying all phase owners.

## 6. Deployment Stages

| Stage | Environment | Validates |
|---|---|---|
| Stage 1 (current) | Laptop, simulated multi-camera RTSP | Software correctness of every feature |
| Stage 2 | On-prem server + real IP cameras on LAN | Real-world detection/re-ID accuracy, dashboard under real load |
| Stage 3 | Edge GPU hardware (Jetson-class) at a test site | Real-time performance, power/resilience features, camera tamper detection under field conditions |
| Stage 4 | Multi-BOP LAN/radio link | Cross-BOP federation protocol |

Do not claim Stage 3/4 validation until actually tested at that stage — the PRD explicitly scopes current work to Stage 1.
