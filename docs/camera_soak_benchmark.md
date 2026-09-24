# Camera Count Soak Benchmark (edge capacity)

Measured with `scripts/bench_cameras.py` on test hardware (RTX 4050 laptop GPU), production edge topology: one shared DetectionService (YOLOv8n, CUDA via ultralytics auto-device), one shared ReIDService (OSNet + vehicle ReID, ONNX GPU), N CameraWorkers at target_fps=10, force_mode=normal, face/plate disabled (run_all defaults).

Ingest source: repo footage files (Docker daemon unavailable in this environment — RTSP transport overhead not included; GPU/queue/worker load identical to production). Health: real fusion server (uvicorn, fresh temp SQLite), health POST every 30 frames; detect latency budget 100 ms (`DETECT_LATENCY_BUDGET_MS`), guard trips reduced_accuracy_mode after 3 consecutive over-budget p95 evaluations (production camera_worker logic).

Warmup 30s (discarded), measure 60s per K, cooldown 30s between K values (thermal settle). GPU temperature recorded at each K start/end (nvidia-smi).

| K | Verdict | Per-camera detect p95 ms (max) | Achieved FPS (median) | Guard tripped | GPU C (start->end) |
|---:|:---:|---|---:|:---:|:---:|
| 1 | stable | 65 | 10.0 | no | 64->71 |
| 2 | stable | 70, 59 | 9.9 | no | 70->74 |
| 3 | stable | 45, 44, 45 | 9.9 | no | 73->75 |
| 4 | degraded | 154, 140, 159, 152 | 8.3 | yes | 73->77 |
| 6 | degraded | 256, 232, 250, 265, 255, 264 | 5.2 | yes | 73->75 |

**Highest stable camera count at target_fps=10 (all cameras within 100 ms detect p95 budget, no reduced_accuracy_mode): K = 3**

Per-camera detail:

| K | Camera | p95 max ms | p95 median ms | FPS | reduced (any) | status |
|---:|---|---:|---:|---:|:---:|---|
| 1 | k1-cam1 | 65 | 27 | 10.0 | no | ok |
| 2 | k2-cam1 | 70 | 53 | 9.9 | no | ok |
| 2 | k2-cam2 | 59 | 51 | 9.8 | no | ok |
| 3 | k3-cam1 | 45 | 20 | 9.9 | no | ok |
| 3 | k3-cam2 | 44 | 28 | 9.9 | no | ok |
| 3 | k3-cam3 | 45 | 30 | 9.9 | no | ok |
| 4 | k4-cam1 | 154 | 138 | 8.3 | yes | ok |
| 4 | k4-cam2 | 140 | 124 | 8.1 | yes | ok |
| 4 | k4-cam3 | 159 | 138 | 8.3 | yes | ok |
| 4 | k4-cam4 | 152 | 139 | 8.3 | yes | ok |
| 6 | k6-cam1 | 256 | 231 | 5.2 | yes | ok |
| 6 | k6-cam2 | 232 | 226 | 5.0 | yes | ok |
| 6 | k6-cam3 | 250 | 223 | 5.2 | yes | ok |
| 6 | k6-cam4 | 265 | 224 | 5.2 | yes | ok |
| 6 | k6-cam5 | 255 | 218 | 5.0 | yes | ok |
| 6 | k6-cam6 | 264 | 233 | 5.3 | yes | ok |

Scope notes: footage ingest (no RTSP decode/network); face/plate sub-services off (run_all defaults); SQLite fusion DB. PRD target is 2-3 cameras — compare max_stable against that.
