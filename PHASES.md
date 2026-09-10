# IBVAP — Phased Execution Plan

No fixed deadline; team of 5+. Phases are sequenced by dependency, not by calendar week — a phase starts when its dependencies are stable, not on a fixed date. Each phase ends with a **working demo of that phase's features on real (or realistically simulated) input** before the next phase builds on top of it.

---

## Phase 0 — Foundation
**Goal:** Everyone can run the system end-to-end on dummy data before any real feature exists.

- Set up shared repo, branching strategy, CI (even a minimal one).
- Stand up FastAPI backbone with health-check endpoint.
- Stand up PostgreSQL with the schema for `DetectionEvent`, `FootprintEntry`, `Alert` (frozen contracts from ARCHITECTURE.md).
- Build simulated multi-camera RTSP ingestion: `mediamtx` + looped multi-angle footage, or phone IP-camera apps, feeding 2–3 "camera" streams.
- Confirm every team member can pull a stream, hit the API, and query the DB locally.

**Exit criteria:** A no-op pipeline runs: fake detection event → written to DB → visible via a basic API call. Everyone's dev environment works identically.

**Owner:** Whole team (pair up for setup, don't let one person become a bottleneck/single point of knowledge).

---

## Phase 1 — Detection & Tracking
**Features:** #1 Human detection & tracking, #2 Vehicle detection & classification, #7 Night-time detection, #23 Weather-adaptive detection.

- Integrate YOLOv8n per stream.
- Integrate ByteTrack for per-camera track continuity.
- Add brightness-based night-mode branch.
- Add visibility estimator + dehazing/contrast branch for weather adaptation; tag low-confidence detections during poor visibility.

**Exit criteria:** Live demo — walk in front of a real/simulated camera, see a bounding box + track ID rendered in real time, at both normal and low-light/simulated-poor-visibility conditions.

**Owner:** 1–2 engineers.

---

## Phase 2 — Cross-Camera Identity (highest priority — the differentiator)
**Features:** #10 Cross-camera digital footprint chain, #25 Self-calibrating camera health.

- Integrate OSNet (person) / vehicle-ReID embeddings into the detection pipeline.
- Build the fusion server's cosine-similarity matching engine across camera streams.
- Build the footprint chain writer: first-seen → hops → last-seen, with timestamps and camera IDs.
- Build camera drift detection: compare live frame to a stored reference frame per camera.

**Exit criteria:** Live demo — walk from one camera's field of view into another's, and see the footprint chain update in real time on a raw API response or basic viewer, correctly identifying it as the same object across both cameras.

**Owner:** 1–2 engineers, most experienced with ML — this is the hardest and most important phase.

---

## Phase 3 — Security & Integrity Layer (self-contained, can start immediately after Phase 0)
**Features:** #12 Tamper-evident local ledger, #19 Camera tamper/blinding detection, #21 Local offline watchlist matching.

- Implement hash-chain: every `FootprintEntry`/`Alert` write includes `hash(entry + previous_hash)`.
- Build a verification routine that walks the chain and flags breaks.
- Implement frame-diff heuristics for full-frame darkness, blur, and frozen-frame detection → distinct "camera compromised" alert type.
- Build encrypted local watchlist storage + embedding comparison at detection time.

**Exit criteria:** Live demo — (a) manually edit a stored ledger entry in the DB, run verification, show it flagged as broken; (b) cover a camera lens, show a "camera compromised" alert fire; (c) add a face/plate to the watchlist, show a match fire correctly.

**Owner:** 1 engineer — does not need to wait on Phase 1/2 to start most of this.

---

## Phase 4 — Alerting & Intelligence
**Features:** #5 Virtual fence intrusion detection, #6 Suspicious activity detection, #8 Real-time alert generation & event logging, #14 Predictive threat scoring, #11 Two-speed alerting (trajectory prediction + AI enrichment), #4 ANPR.

- Build the deterministic rule engine: polygon ROI vs. tracked centroid.
- Build rule-based suspicious activity checks (loitering timer, path reversal, group clustering).
- Build the threat scoring function (time-of-day + historical ROI frequency + trajectory confidence).
- Build Kalman-filter trajectory projection.
- Build the async AI enrichment service (local LLM/VLM) that appends explanation + projection to an already-fired alert.
- Build ANPR pipeline (plate detector + OCR) as a parallel, separable workstream.

**Exit criteria:** Live demo — a tracked object crossing a configured ROI fires an alert within acceptable latency, appears immediately on a basic viewer, and is enriched with an AI explanation + trajectory overlay within a few seconds, without the initial alert having been delayed.

**Owner:** 1–2 engineers (ANPR can be a separate person working in parallel).

---

## Phase 5 — Interfaces
**Features:** Command dashboard, #24 Patrol companion app, #15 Explainable alert overlay, #20 Adversarial blind-spot mapping.

- Build the dashboard: live feed view, alert queue (priority-ranked by threat score), footprint chain viewer, ledger status indicator, blind-spot map, ROI configuration UI, searchable event log.
- Build clip overlay rendering (bbox + trajectory + crossed ROI line burned into saved clips).
- Build the blind-spot computation: given all configured camera ROIs, compute and visualize uncovered zones.
- Build the LAN-only patrol companion app against the same API surface as the dashboard.

**Exit criteria:** A non-technical person can open the dashboard, see live alerts with overlays, view a footprint chain, and see the blind-spot map — without needing anyone to explain the underlying pipeline.

**Owner:** 1–2 engineers; start once Phase 4's API is stable to avoid rebuilding integration glue.

---

## Phase 6 — Resilience Hardening (revisit once core is stable)
**Features:** #17 Degraded-mode resilience, #22 Power/hardware resilience, #16 Offline model update mechanism.

- Implement coverage-gap flagging on camera disconnect.
- Implement automatic fallback to a lighter model under compute load, with a visible UI indicator.
- Implement checkpoint/resume logic for the ledger and in-progress clips.
- Implement low-power fallback mode (reduce active cameras/FPS).
- Implement signed model package format + hash verification for offline updates.

**Exit criteria:** Simulated failure tests pass (kill a camera feed, throttle CPU, simulate a crash mid-write) with the system recovering or clearly flagging degraded state each time. Mark clearly as "validated in simulation" until tested on real edge/power hardware (Stage 3 in ARCHITECTURE.md).

**Owner:** Whole team, rotating — this phase benefits from fresh eyes across the whole system.

---

## Deferred (documented, not built this cycle)
- **#13 Cross-BOP federation** — design the sync protocol, demo on two LAN nodes simulating adjacent BOPs. Do not claim field-tested multi-BOP validation.
- **#18 Multi-modal sensor fusion** — documented as an extension point in ARCHITECTURE.md only. No stub implementation, since there is no real sensor input to validate against.

---

## Cross-Phase Rules
- No phase begins consuming another phase's output until that output matches the frozen data contract in ARCHITECTURE.md Section 5.
- Every phase ends with a **live demo on real/simulated input**, not a description of what should work.
- Any deviation from "fully working, not faked" (see AGENTS.md Section 3) must be flagged in the phase's exit review, not discovered later.
