# YOLO Detector Benchmark (v8n vs v8m)

Measured with `scripts/bench_yolo.py` on repo footage (`footage/cam1.mp4`), imgsz=640. Re-run per device; rows merge by (model, device).

| Model | Device | Frames | Mean ms | p50 ms | p95 ms | FPS |
|---|---|---:|---:|---:|---:|---:|
| yolov8n.pt | cpu | 30 | 80.0 | 81.4 | 99.9 | 12.5 |
| yolov8m.pt | cpu | 30 | 422.2 | 408.2 | 501.5 | 2.4 |
| yolov8n.pt | cuda | 50 | 28.9 | 25.0 | 42.2 | 34.6 |
| yolov8m.pt | cuda | 50 | 34.2 | 33.2 | 46.2 | 29.3 |

Real-time budget: >= 25 FPS end-to-end per camera counts as real-time for this project's edge tier.
