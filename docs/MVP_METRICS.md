# MVP Metrics Table (measured on test hardware)

All numbers below are **real measurements** on the team's test laptop
(NVIDIA RTX 4050 6 GB, Windows, Python 3.13, torch 2.14.0+cu126 /
onnxruntime-gpu 1.20.2) — no estimated or simulated values. Every row links
the raw benchmark report and the script that produced it. Re-run any script
to reproduce (usage is in each script's docstring).

| # | Metric | Result | Source |
|---|---|---|---|
| 1 | Detection latency (fusion tier, yolov8m CUDA, imgsz 640) | mean 22.0 ms / p50 20.6 / **p95 27.5 ms** (45.6 FPS) | `scripts/bench_yolo.py` → `docs/yolo_benchmark.md` |
| 1b | Detection latency (edge tier, yolov8n CUDA, imgsz 640) | mean 28.9 ms / p50 25.0 / **p95 42.2 ms** (34.6 FPS) | `scripts/bench_yolo.py` → `docs/yolo_benchmark.md` |
| 2 | Tracking throughput (production `Tracker.update()`) | real YOLOv8n detections: p95 **0.149 ms/update** (p50 0.117); synthetic worst-case 50 boxes: p95 7.45 ms → **223 updates/s**; backend `_SimpleByteTracker` | `scripts/bench_tracker.py` → `docs/tracker_benchmark.md` |
| 3a | Matching accuracy — gated evals (all 6 gates pass) | vehicle Rank-1 **86.5%** (VeRi, thr 0.60); person temporal **78.1%**, cross-camera 46.9%, margin 0.312; plate precision **99.9%**; face Rank-1 **95.0%** (LFW) | `pytest tests/test_eval_gates.py` (6 passed, 233 s) |
| 3b | Cross-camera link rate — live production path | **100% (20/20)** VeRi identity pairs linked through `_ingest_event()` + `MatchingEngine` (mean same-id cosine 0.870) | `scripts/bench_link_rate.py` → `docs/link_rate_benchmark.md` |
| 4 | Alert generation time (event receipt → alert persisted) | mean 24.9 ms / p50 22.1 / **p95 24.8 ms** (30/30 alerts fired; full `_ingest_event` wall p95 33.6 ms) | `scripts/bench_alert.py` → `docs/alert_benchmark.md` |
| 5 | Cameras supported (target 10 FPS, 100 ms detect p95 budget) | **K = 3 stable** (per-cam p95 44–70 ms, achieved 9.9–10.0 FPS, guard never tripped); K = 4 degraded (p95 140–159 ms, 8.3 FPS, guard tripped); K = 6 degraded (p95 232–265 ms, 5.2 FPS) → **meets PRD target of 2–3 cameras** | `scripts/bench_cameras.py` → `docs/camera_soak_benchmark.md` |
| 6 | Evidence (ledger) verification time | pure SHA-256 recompute **1.0 µs/entry** (10k entries = 10.1 ms); operator DB run (`verify_all_chains`) **8.6 µs/entry** (1k = 8.5 ms, 10k = 86.2 ms); tamper detection confirmed at every size | `scripts/bench_ledger.py` → `docs/ledger_benchmark.md` |

## Notes and caveats (read with the numbers)

- **Row 3b deviation (flagged):** the original plan proposed cam1→cam2
  footage walk-throughs; repo footage has no verified cross-camera identity
  ground truth, so a footage success % would be unverifiable. VeRi-776
  provides real cross-camera ground truth through the same production code
  path (`ReIDService.extract_embedding` → `_ingest_event` →
  `MatchingEngine`, vehicle threshold 0.60 cosine, 5-minute window).
  Detection-box quality is covered by the gated Rank-1 metric (3a), since
  this bench feeds full-image crops.
- **Bug found and fixed by these benches:** vehicle Re-ID preprocessing
  normalized in HWC layout against a `(3,1,1)` ImageNet mean — every vehicle
  embedding failed (`edge/reid_service.py:_preprocess_crop`). Fixed (transpose
  before normalize), red-green verified with
  `tests/test_reid_service.py::test_vehicle_preprocess_and_real_inference`.
  Row 3b numbers are post-fix; before the fix the production path returned
  no vehicle embeddings at all.
- **Row 5 ingest source:** repo footage files (Docker daemon unavailable in
  this environment) — RTSP transport overhead is NOT included; GPU, queue,
  and worker load are identical to production. Face/plate sub-services off
  (`run_all` defaults). Warmup 30 s (discarded), measure 60 s, cooldown 30 s
  between K values, GPU temperature recorded per K (64–77 °C, no thermal
  runaway). Run-to-run variance exists near the budget boundary (early
  exploratory runs tripped at lower K during warmup-contaminated windows);
  the reported run uses a full capacity curve (all K values, longer warmup).
- **Row 4 definition (user-locked):** `Alert.created_at −
  DetectionEvent.timestamp` (event receipt → alert row with ledger hash).
  Measured at `_ingest_event()` entry; HTTP/JSON transport (~1–3 ms) is
  excluded. AI enrichment is async and out of scope (AGENTS.md Rule 4).
- **Rows 1/4/6 DB:** single-process SQLite (temp DBs). PostgreSQL adds
  commit latency under concurrency; ledger numbers are hash-bound and
  DB-layer bound respectively (both reported).
- Row 2 real-mode mean (8.8 ms) is inflated by the first-call outlier;
  p50/p95 (0.117/0.149 ms) reflect steady state. Synthetic passes exercise
  Kalman + Hungarian with 5/15/30/50 boxes.

## Reproduce

```powershell
venv\Scripts\python.exe scripts\bench_yolo.py        # row 1 (already in docs/yolo_benchmark.md)
venv\Scripts\python.exe scripts\bench_tracker.py      # row 2
venv\Scripts\python.exe -m pytest tests\test_eval_gates.py   # row 3a
venv\Scripts\python.exe scripts\bench_link_rate.py    # row 3b
venv\Scripts\python.exe scripts\bench_alert.py        # row 4
venv\Scripts\python.exe scripts\bench_cameras.py      # row 5 (~13 min)
venv\Scripts\python.exe scripts\bench_ledger.py       # row 6
```
