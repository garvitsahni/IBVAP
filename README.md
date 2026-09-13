# IBVAP — Intelligent Border Video Analytics Platform

> A fully sovereign, edge-native video analytics platform that transforms existing BOP CCTV into a self-auditing surveillance mesh — every object tracked across every camera with a tamper-evident local footprint, alerts fired at machine speed before AI is ever involved, and zero data leaving the post.

**Organization:** Ministry of Home Affairs · Sashastra Seema Bal (SSB), Police II Division

---

## What IBVAP Does

| Capability | How |
|---|---|
| **Real-time intrusion detection** | YOLOv8s + ByteTrack per camera, virtual fence rule engine |
| **Cross-camera object tracking** | OSNet re-ID embeddings, cosine similarity matching across cameras |
| **Tamper-evident audit trail** | SHA-256 hash-chained ledger — every footprint entry linked to the previous |
| **License plate recognition** | EasyOCR + YOLOv8 plate detection, multi-region cropping |
| **Night / low-light operation** | Adaptive CLAHE preprocessing, browser exposure boost, model switching |
| **Camera health monitoring** | Frame-diff heuristics for tamper, blinding, drift — independent of detection pipeline |
| **Local watchlist matching** | Encrypted face/plate embedding store, compared at detection time |
| **AI enrichment (async)** | Natural-language explanation + trajectory projection — never blocks alert delivery |

**Non-negotiables:** Deterministic engines own all alert decisions. No raw video leaves the BOP. Every feature works on real input — nothing faked.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, PostgreSQL (pgvector) |
| Detection | YOLOv8s (CPU), ONNX Runtime, insightface, ultralytics |
| OCR | EasyOCR |
| Frontend | React 19, TypeScript 6, Vite 8, TailwindCSS v4, Leaflet, framer-motion |
| Infrastructure | Docker Compose, MediaMTX (RTSP), MinIO (clips), PostgreSQL 16 |
| Testing | pytest (394 tests, 0 failures) |

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 22+
- Docker & Docker Compose
- PostgreSQL 16+ (or use Docker)

### 1. Clone & configure

```bash
git clone https://github.com/garvitsahni/IBVAP.git
cd IBVAP
cp .env.example .env
```

### 2. Start infrastructure

```bash
docker compose up -d postgres mediamtx minio
```

This starts:
- **PostgreSQL** on port `5434` (with pgvector)
- **MediaMTX** RTSP server on port `8554`
- **MinIO** object storage on port `9000` / console `9001`

### 3. Backend setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
```

### 4. Start the fusion server

```bash
python -m uvicorn fusion_server.main:app --host 0.0.0.0 --port 8000
```

The API is now at `http://localhost:8000`. Dashboard at `http://localhost:8000/dashboard/`.

### 5. Build the dashboard (for production)

```bash
cd dashboard
npm install
npm run build
cd ..
```

Restart the fusion server — the built SPA is served automatically from `/dashboard/`.

### 6. Run tests

```bash
python -m pytest tests/ -x -q
```

---

## Project Structure

```
IBVAP/
├── fusion_server/              # FastAPI backend (BOP Fusion Server)
│   ├── main.py                 # App entrypoint, SPA serving, CORS
│   ├── api/
│   │   ├── events.py           # POST /api/v1/events — detection event ingestion
│   │   ├── alerts.py           # CRUD + SSE stream for alerts
│   │   ├── footprint.py        # Footprint chain retrieval & verification
│   │   ├── watchlist.py        # Face/plate watchlist CRUD
│   │   └── routes/
│   │       ├── detect.py       # POST /api/v1/detect — YOLOv8s + EasyOCR inference
│   │       ├── cameras.py      # Camera CRUD + health + heartbeat
│   │       ├── ledger.py       # Hash-chain ledger status & verification
│   │       ├── dashboard.py    # Aggregated dashboard statistics
│   │       ├── plates.py       # Plate detection history
│   │       ├── rois.py         # Region-of-interest management
│   │       ├── streams.py      # HLS stream serving
│   │       └── coverage.py     # Blind-spot analysis
│   ├── core/
│   │   ├── rule_engine.py      # ROI polygon vs. centroid — deterministic alerts
│   │   ├── ledger.py           # SHA-256 hash-chain implementation
│   │   ├── reid_matcher.py     # Cross-camera cosine similarity matching
│   │   ├── threat_scoring.py   # Deterministic threat scoring
│   │   ├── trajectory.py       # Kalman filter trajectory prediction
│   │   ├── anpr.py             # ANPR pipeline (YOLOv8 plate + EasyOCR)
│   │   └── alert_ledger.py     # Alert hash-chain linkage
│   ├── services/
│   │   ├── footprint_writer.py # Synchronous ledger writer (tamper-evidence)
│   │   ├── alert_pipeline.py   # Alert creation + SSE broadcast
│   │   ├── broadcaster.py      # In-memory pub/sub for SSE
│   │   ├── watchlist_matcher.py# Face/plate watchlist matching
│   │   ├── camera_health_store.py # In-memory camera health tracking
│   │   ├── hls_manager.py      # HLS segment management
│   │   └── resilience_aggregator.py # System health aggregation
│   └── db/
│       ├── models.py           # SQLAlchemy models
│       ├── session.py          # Database session management
│       └── schema.sql          # DDL (PostgreSQL)
│
├── edge/                       # Edge processing node
│   ├── ingestion.py            # RTSP stream reader
│   ├── detector.py             # YOLOv8 detection wrapper
│   ├── tracker.py              # ByteTrack per-camera tracking
│   ├── reid_service.py         # OSNet embedding extraction
│   ├── face_detector.py        # InsightFace detection
│   ├── face_embedding.py       # InsightFace embedding extraction
│   ├── plate_detector.py       # YOLOv8 plate detection
│   ├── plate_ocr.py            # EasyOCR plate reading
│   ├── camera_health.py        # Tamper/blinding/drift detection
│   ├── night_weather.py        # Brightness-adaptive preprocessing
│   ├── event_publisher.py      # Sends events to fusion server
│   └── run_camera.py           # Per-camera worker process
│
├── dashboard/                  # React command dashboard
│   ├── src/
│   │   ├── pages/              # Dashboard, Alerts, History, Map, Settings
│   │   ├── components/
│   │   │   ├── camera/         # Camera grid, feeds, detection overlays
│   │   │   ├── alert/          # Alert feed, detail panel, SSE integration
│   │   │   ├── layout/         # Sidebar, TopBar, ConsoleLayout
│   │   │   └── ui/             # Button, StatusBadge, StatCard
│   │   ├── services/           # API client, SSE client
│   │   ├── hooks/              # useSSE, useAuth
│   │   └── types/              # TypeScript interfaces
│   └── vite.config.ts          # Vite config (base: /dashboard/)
│
├── patrol_app/                 # LAN-only patrol companion app
├── tests/                      # 394 tests — detection, ledger, alerts, re-ID
├── scripts/                    # Setup & utility scripts
├── models/                     # ONNX model files
│
├── docker-compose.yml          # PostgreSQL + MediaMTX + MinIO
├── requirements.txt            # Python dependencies
├── .env.example                # Environment configuration template
│
├── IBVAP_PRD.md                # Product requirements document
├── ARCHITECTURE.md             # System topology & data contracts
├── PHASES.md                   # Phased execution plan
├── AGENTS.md                   # Coding agent guardrails
├── RULES.md                    # Team working agreement
├── DESIGN_SYSTEM.md            # UI/UX design system
└── IMPLEMENTATION.md           # Build instructions
```

---

## API Reference

All API routes are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/detect` | YOLOv8s detection + plate OCR on base64 image |
| `POST` | `/events` | Ingest a detection event from edge node |
| `GET` | `/events` | List detection events (filterable by camera) |
| `GET` | `/alerts` | List alerts (paginated) |
| `GET` | `/alerts/{id}` | Get alert details |
| `POST` | `/alerts/{id}/acknowledge` | Acknowledge an alert |
| `GET` | `/alerts/stream` | SSE stream — real-time alert events |
| `GET` | `/cameras` | List registered cameras |
| `POST` | `/cameras` | Register a new camera |
| `DELETE` | `/cameras/{id}` | Remove a camera |
| `POST` | `/cameras/{id}/heartbeat` | Camera health heartbeat |
| `GET` | `/footprint/{object_id}` | Get footprint chain for an object |
| `GET` | `/footprint/{object_id}/verify` | Verify footprint chain integrity |
| `GET` | `/ledger/status` | Hash-chain ledger verification status |
| `GET` | `/dashboard/stats` | Aggregated dashboard statistics |
| `GET` | `/rois` | List regions of interest |
| `POST` | `/rois` | Create a region of interest |
| `GET` | `/plates` | List detected plates |
| `GET` | `/watchlist` | List watchlist entries |
| `POST` | `/watchlist` | Add face/plate to watchlist |
| `GET` | `/coverage/blind-spots` | Camera coverage analysis |
| `GET` | `/system/health` | System health check |

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                      BOP PERIMETER                       │
│                                                          │
│  [Camera 1]   [Camera 2]   [Camera 3]   ...             │
│      │             │             │                        │
│      ▼             ▼             ▼                        │
│  ┌─────────────────────────────────────────┐             │
│  │         EDGE PROCESSING NODE(S)          │             │
│  │  RTSP ingestion → YOLOv8s → ByteTrack    │             │
│  │  Re-ID embeddings · Camera health        │             │
│  │  Face/plate detection · Night adaptation  │             │
│  └──────────────────┬──────────────────────┘             │
│                     │ structured events + embeddings      │
│                     ▼                                     │
│  ┌─────────────────────────────────────────┐             │
│  │         BOP FUSION SERVER                │             │
│  │  Cross-camera re-ID · Footprint ledger   │             │
│  │  Rule engine · Threat scoring            │             │
│  │  Watchlist matching · AI enrichment       │             │
│  │  PostgreSQL · FastAPI · SSE streaming     │             │
│  └──────────────────┬──────────────────────┘             │
│           ┌─────────┴──────────┐                         │
│           ▼                    ▼                          │
│   [Command Dashboard]  [Patrol App]                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://ibvap:ibvap@localhost:5434/ibvap` | PostgreSQL connection string |
| `YOLO_MODEL` | `yolov8n.pt` | YOLO model weights (n=nano, s=small) |
| `CONF_THRESHOLD` | `0.3` | Detection confidence threshold |
| `REID_THRESHOLD` | `0.75` | Re-ID matching threshold |
| `FUSION_SERVER_PORT` | `8000` | Backend API port |

---

## Testing

```bash
# Run full test suite
python -m pytest tests/ -x -q

# Run with verbose output
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_ledger.py -v
```

Current status: **394 passed, 0 failed, 0 skipped**.

---

## Documentation

| Document | Purpose |
|---|---|
| [IBVAP_PRD.md](IBVAP_PRD.md) | Product requirements — problem, vision, 25 features, success criteria |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System topology, component design, data contracts |
| [PHASES.md](PHASES.md) | Phased execution plan with exit criteria |
| [AGENTS.md](AGENTS.md) | Coding guardrails — non-negotiable architectural rules |
| [RULES.md](RULES.md) | Team working agreement — git workflow, testing standard |
| [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | UI/UX design system for dashboard & patrol app |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | Step-by-step build instructions |

---

## License

Government of India · Ministry of Home Affairs · Sashastra Seema Bal
