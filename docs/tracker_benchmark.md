# Tracker Benchmark

Measured with `scripts/bench_tracker.py` (per-call `Tracker.update()` timing; fresh `Tracker` per pass).

**real**: production detections — `DetectionService._run_inference` (YOLOv8n, conf>=0.35, TARGET_CLASSES) over 100 frames of `footage/cam1.mp4` replayed through the tracker.

**synthetic**: 200 frames per pass, N boxes with smooth random-walk motion (Kalman predict/update + Hungarian matching active).

| Input | Frames | Mean ms | p50 ms | p95 ms | Updates/s |
|---|---:|---:|---:|---:|---:|
| real (YOLOv8n dets) | 100 | 8.847 | 0.117 | 0.149 | 113 |
| synthetic 5 boxes | 200 | 0.448 | 0.423 | 0.636 | 2231 |
| synthetic 15 boxes | 200 | 1.192 | 1.069 | 2.012 | 839 |
| synthetic 30 boxes | 200 | 3.067 | 2.948 | 5.157 | 326 |
| synthetic 50 boxes | 200 | 4.474 | 4.078 | 7.452 | 223 |

Tracker backend on this host: (backend=_SimpleByteTracker, avg dets/frame=0.72, avg tracks/frame=0.69)

Budget context: one camera at target_fps=10 needs one update every 100ms; tracker cost must stay well under that alongside detection (see yolo_benchmark.md) and ReID.
