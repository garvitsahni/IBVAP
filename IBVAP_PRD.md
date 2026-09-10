# Product Requirements Document
## IBVAP — Intelligent Border Video Analytics Platform

**Organization:** Ministry of Home Affairs
**Department:** Sashastra Seema Bal (SSB), Police II Division
**Category:** Software
**Theme:** Blockchain & Cybersecurity
**Document status:** Final — v1.0

---

## 1. Problem Statement

Border security forces deploy CCTV at Border Out Posts (BOPs), check posts, and border roads for surveillance, but conventional systems only provide recording and live monitoring — requiring continuous human observation. Advanced capabilities like facial recognition, ANPR, intrusion detection, and object tracking typically require proprietary hardware, making large-scale deployment in remote border areas costly and difficult.

## 2. Product Vision

IBVAP transforms existing CCTV infrastructure into a self-auditing, tamper-evident surveillance mesh — entirely through software. Every object is tracked across every camera at a post with an immutable local footprint, alerts fire at machine speed before AI is ever involved, and **no data ever leaves the BOP**.

**One-line pitch:** *A fully sovereign, edge-native video analytics platform that gives border posts machine-speed alerts, cross-camera object continuity, and tamper-proof evidence — without a single byte leaving the post.*

## 3. Goals

- Eliminate dependence on expensive dedicated surveillance hardware (FRS/ANPR appliances).
- Deliver real-time, low-latency alerts for intrusions and security incidents.
- Guarantee full data sovereignty — all inference, storage, and alerting happen on-prem at the BOP.
- Provide a tamper-evident evidentiary trail suitable for chain-of-custody purposes.
- Give operators cross-camera situational awareness, not isolated single-feed views.
- Be deployable on existing IP camera infrastructure with no proprietary hardware lock-in.
- Support integration with existing command and control (C2) systems via open APIs.

## 4. Non-Goals

- Building a cloud-hosted or multi-tenant SaaS version — this is explicitly an on-prem, sovereign system.
- Multi-modal sensor fusion (seismic/acoustic/thermal) — documented as a future extension point only, not built, since no such sensors are available to validate against.
- Field-hardened deployment on actual border-post edge hardware — current phase targets laptop/on-prem validation; edge hardware deployment is a defined later phase.

## 5. System Architecture

### 5.1 Topology (2-tier, fully on-prem)

**Edge tier** — one lightweight processing node per camera or camera cluster. Pulls RTSP streams from existing IP cameras; runs detection and tracking locally. No raw video leaves this tier except as short, event-triggered clips.

**BOP Fusion Server** — one server per post (or per cluster of nearby posts). Hosts the re-identification/fusion engine, footprint ledger, alert engine, local watchlist database, dashboard, and all storage. No cloud tier exists in this architecture. An optional, deliberate one-way sync of alert *summaries* to HQ may exist, but the system is never dependent on it for real-time operation.

### 5.2 Data Flow

1. Camera → RTSP → Edge detection/tracking → local event object (detection + track ID + embedding)
2. Edge → BOP Fusion Server → cross-camera re-ID matching → footprint chain written to ledger
3. Rule engine evaluates ROI/geometry against tracked objects → instant deterministic alert
4. Alert → hash-chained ledger entry + annotated clip generation
5. AI enrichment (non-blocking, async) → natural-language explanation + trajectory projection appended to the alert
6. Dashboard and patrol app subscribe to the alert/footprint stream over local network only

## 6. Feature Set (Finalized)

### 6.1 Core Detection & Tracking
| # | Feature | Description |
|---|---|---|
| 1 | Human detection & tracking | YOLOv8n + ByteTrack per camera stream |
| 2 | Vehicle detection & classification | Same pipeline, vehicle-class model head |
| 3 | Face detection | RetinaFace/SCRFD; detection-only by default |
| 4 | ANPR | YOLO-based plate detector + PaddleOCR, tuned to Indian plate formats |
| 5 | Virtual fence intrusion detection | Deterministic polygon-ROI geometry check against tracked centroids — never ML-decided |
| 6 | Suspicious activity detection | Rule-based: loitering duration, erratic path reversal, group clustering at anomalous hours |
| 7 | Night-time movement detection | Brightness-triggered switch to low-light-tuned weights / enhancement pass |
| 8 | Real-time alert generation & event logging | Alerts fire on rule violation, all events logged to the local database |

### 6.2 Core Differentiators
| # | Feature | Description |
|---|---|---|
| 9 | Total data sovereignty | All inference, storage, and alerting on-prem at the BOP; no cloud dependency |
| 10 | Cross-camera digital footprint chain | Re-ID embeddings (OSNet/vehicle-ReID) link an object across cameras into a single timestamped chain: first-seen camera → intermediate hops → last-seen camera |
| 11 | Two-speed alerting | Deterministic alert fires instantly (ms); AI explanation + trajectory prediction (Kalman filter, upgradeable to LSTM) arrive seconds later, non-blocking |

### 6.3 Security, Integrity & Intelligence Layer
| # | Feature | Description |
|---|---|---|
| 12 | Tamper-evident local ledger | Hash-chained footprint/alert records (Merkle/hash-chain); any post-hoc edit breaks the chain and is detectable |
| 14 | Predictive threat scoring | Alerts ranked by time-of-day risk, historical incident frequency at that ROI, and trajectory confidence |
| 15 | Explainable alert overlay | Bounding box + trajectory arrow + crossed ROI line burned into the saved alert clip |
| 19 | Camera tamper/blinding detection | Frame-diff heuristics detect covered lenses, sprayed/blinded cameras, frozen/hijacked feeds; fires a distinct "camera compromised" alert |
| 20 | Adversarial blind-spot mapping | Computes and visualizes coverage gaps between camera fields of view across a BOP's ROI configuration |
| 21 | Local offline watchlist matching | Encrypted, on-device face/plate watchlist; matching happens entirely locally, no data leaves the post |
| 23 | Weather/environment-adaptive detection | Visibility estimator triggers dehazing/contrast enhancement; alerts issued in poor visibility are flagged "reduced confidence" |
| 25 | Self-calibrating camera health | Compares live scene to a stored reference frame per camera; flags "needs recalibration" on detected drift |

### 6.4 Interfaces
| # | Feature | Description |
|---|---|---|
| — | Command dashboard | Live feeds, alert queue (priority-ranked), footprint chain viewer, blind-spot map, ledger status, virtual fence configuration, searchable event log; REST/webhook hooks for existing C2 integration |
| 24 | Patrol companion app | LAN-only mobile app for the BOP's patrol team; receives alerts, footprint chains, and trajectory overlays over local network, no internet |

### 6.5 Resilience Layer (validated in later phase, on real hardware)
| # | Feature | Description |
|---|---|---|
| 17 | Degraded-mode resilience | Coverage-gap flagging on camera failure; auto-fallback to a lighter model under compute load, with a visible "reduced accuracy mode" indicator |
| 22 | Power/hardware resilience | Checkpoint-resume on power loss so ledger/clips are never corrupted; low-power fallback mode on backup power |
| 16 | Offline model update mechanism | Signed model packages, hash-verified before load, transferred via a controlled local channel (e.g. USB) — no internet required |

### 6.6 Deferred / Documented Extension Points (not built in this phase)
| # | Feature | Status |
|---|---|---|
| 13 | Cross-BOP federation | Protocol designed; demoed on LAN between two nodes simulating adjacent BOPs, not field-tested across real posts |
| 18 | Multi-modal sensor fusion | Documented as a future extension point only — no seismic/acoustic/thermal hardware available to validate against |

## 7. Build Phases

| Phase | Scope | Owner(s) |
|---|---|---|
| 0 | Foundation: simulated multi-camera RTSP ingestion, shared repo, FastAPI backbone, DB schema | Whole team |
| 1 | Detection & tracking, night-mode, weather-adaptive branches | 1–2 engineers |
| 2 | Cross-camera re-ID, footprint chain, camera drift detection | 1–2 engineers (highest priority — core differentiator) |
| 3 | Hash-chain ledger, camera tamper detection, local watchlist matching | 1 engineer (self-contained, can start immediately) |
| 4 | Virtual fence + alerting, threat scoring, trajectory prediction, AI enrichment, ANPR | 1–2 engineers |
| 5 | Command dashboard, patrol companion app | 1–2 engineers (sequenced after Phase 4 API is stable) |
| 6 | Resilience hardening: degraded-mode, power resilience, offline model updates | Whole team, once core is stable |

## 8. Technical Stack

- **Detection/tracking:** YOLOv8n, ByteTrack
- **Re-ID:** OSNet (person), vehicle-ReID model
- **Face detection:** RetinaFace / SCRFD
- **ANPR:** YOLO plate detector + PaddleOCR
- **Trajectory prediction:** Kalman filter (baseline), LSTM (stretch)
- **Backend:** FastAPI (Python)
- **Storage:** PostgreSQL (footprint ledger, alerts, watchlist), local object store for clips
- **Ledger integrity:** custom hash-chain implementation
- **AI enrichment:** local LLM/VLM, non-blocking async service
- **Frontend:** dashboard (React or server-rendered), LAN-only patrol app

## 9. Success Criteria (MVP)

- Live ingestion from 2–3 real or simulated camera feeds with no dropped connections during a demo session.
- Footprint chain correctly links an object moving between at least two cameras in real time.
- Virtual fence alert fires within acceptable latency of a rule violation, with zero false negatives on the tested ROI.
- Ledger tamper demo: editing a stored record is detectably flagged as broken.
- Every shipped feature listed in Sections 6.1–6.4 functions on real (not scripted/faked) input during a live walkthrough.

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Re-ID accuracy degrades under real-world lighting/angle variation | Extensive testing on a fixed, rehearsed camera pair before any live demo |
| Laptop-only hardware limits real-time FPS at scale | Use YOLOv8n at reduced resolution; document GPU/edge requirements for production deployment separately |
| Resilience features (power loss, degraded mode) untestable without real hardware | Build and unit-test logic now; mark as "validated in simulation only" until edge hardware is available |
| Scope creep across a 5-person team with no fixed deadline | Freeze data contracts (event/alert/footprint schemas) at Phase 0 so teams can work in parallel without integration debt |

