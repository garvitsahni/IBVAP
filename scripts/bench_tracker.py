#!/usr/bin/env python3
"""
Benchmark the edge tracker (edge/tracker.py) — MVP metrics row 2.

Two measurement modes:
  real      — production detections: DetectionService._run_inference (YOLOv8n,
              TARGET_CLASSES, conf>=0.35) over footage frames, replayed through
              Tracker.update() with per-call timing.
  synthetic — N boxes (default 5/15/30/50) with smooth random-walk motion per
              frame so Kalman predict/update and Hungarian matching both run.

Writes/updates docs/tracker_benchmark.md. Exit 0 after writing the report
(measurement tool, not a gate).

Usage:
    venv\\Scripts\\python.exe scripts\\bench_tracker.py [--frames 100]
        [--synthetic-boxes 5 15 30 50] [--synthetic-frames 200]
        [--video footage/cam1.mp4]
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "tracker_benchmark.md"


def pct(sorted_vals, p):
    return sorted_vals[int(p * (len(sorted_vals) - 1))]


def summarize(latencies_ms, label, extra=""):
    lat = sorted(latencies_ms)
    mean = statistics.mean(lat)
    result = {
        "label": label,
        "n": len(lat),
        "mean_ms": mean,
        "p50_ms": statistics.median(lat),
        "p95_ms": pct(lat, 0.95),
        "fps": 1000.0 / mean if mean > 0 else 0.0,
        "extra": extra,
    }
    print(f"  {label}: mean={result['mean_ms']:.3f}ms "
          f"p50={result['p50_ms']:.3f}ms p95={result['p95_ms']:.3f}ms "
          f"-> {result['fps']:.0f} updates/s {extra}")
    return result


def bench_real(video: Path, frames: int) -> dict:
    """Replay production YOLO detections through Tracker.update()."""
    import cv2
    from edge.detector import DetectionService

    detector = DetectionService(None, None)  # queues unused; we call _run_inference directly
    detector._load_model()

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise FileNotFoundError(video)

    per_frame = []
    h = w = 0
    n = 0
    while n < frames:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        dets = detector._run_inference(frame)
        per_frame.append(dets)
        n += 1
    cap.release()
    if not per_frame:
        raise RuntimeError(f"no frames decoded from {video}")

    from edge.tracker import Tracker
    tracker = Tracker()
    backend = "yolox BYTETracker" if tracker._use_yolox else "_SimpleByteTracker"

    latencies = []
    total_dets = 0
    total_tracks = 0
    for dets in per_frame:
        total_dets += len(dets)
        t0 = time.perf_counter()
        tracks = tracker.update(dets, (h, w))
        latencies.append((time.perf_counter() - t0) * 1000.0)
        total_tracks += len(tracks)

    avg_dets = total_dets / len(per_frame)
    avg_tracks = total_tracks / len(per_frame)
    extra = (f"(backend={backend}, avg dets/frame={avg_dets:.2f}, "
             f"avg tracks/frame={avg_tracks:.2f})")
    return summarize(latencies, "real (YOLOv8n dets)", extra)


def bench_synthetic(box_counts, n_frames: int, frame_shape=(432, 768)) -> list:
    """Random-walk boxes so matching/Kalman paths are exercised."""
    import numpy as np
    from edge.tracker import Tracker

    results = []
    h, w = frame_shape
    rng = np.random.default_rng(42)
    for n_boxes in box_counts:
        # initial boxes: random positions/sizes, half person half vehicle-ish
        boxes = []
        for i in range(n_boxes):
            bw = rng.uniform(0.05, 0.2) * w
            bh = rng.uniform(0.1, 0.3) * h
            x1 = rng.uniform(0, w - bw)
            y1 = rng.uniform(0, h - bh)
            boxes.append({
                "bbox": [x1, y1, x1 + bw, y1 + bh],
                "confidence": float(rng.uniform(0.55, 0.95)),
                "class_id": 0 if i % 2 == 0 else 2,
                "class_name": "person" if i % 2 == 0 else "car",
            })

        tracker = Tracker()
        latencies = []
        for _ in range(n_frames):
            # smooth motion: each box drifts a little (keeps IoU matches alive)
            for b in boxes:
                dx = rng.normal(0, 0.01 * w)
                dy = rng.normal(0, 0.01 * h)
                b["bbox"][0] = float(np.clip(b["bbox"][0] + dx, 0, w - 1))
                b["bbox"][1] = float(np.clip(b["bbox"][1] + dy, 0, h - 1))
                b["bbox"][2] = float(np.clip(b["bbox"][2] + dx, 0, w))
                b["bbox"][3] = float(np.clip(b["bbox"][3] + dy, 0, h))
            dets = [dict(b) for b in boxes]
            t0 = time.perf_counter()
            tracker.update(dets, (h, w))
            latencies.append((time.perf_counter() - t0) * 1000.0)

        backend = "yolox BYTETracker" if tracker._use_yolox else "_SimpleByteTracker"
        r = summarize(latencies, f"synthetic {n_boxes} boxes",
                      f"(backend={backend})")
        results.append(r)
    return results


def write_report(real: dict, synth: list, video: Path, frames: int,
                 synth_frames: int):
    lines = [
        "# Tracker Benchmark",
        "",
        "Measured with `scripts/bench_tracker.py` (per-call `Tracker.update()` "
        "timing; fresh `Tracker` per pass).",
        "",
        f"**real**: production detections — `DetectionService._run_inference` "
        f"(YOLOv8n, conf>=0.35, TARGET_CLASSES) over {real['n']} frames of "
        f"`{video.relative_to(REPO_ROOT).as_posix()}` replayed through the tracker.",
        "",
        f"**synthetic**: {synth_frames} frames per pass, N boxes with smooth "
        "random-walk motion (Kalman predict/update + Hungarian matching active).",
        "",
        "| Input | Frames | Mean ms | p50 ms | p95 ms | Updates/s |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    rows = [real] + synth
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['n']} | {r['mean_ms']:.3f} | "
            f"{r['p50_ms']:.3f} | {r['p95_ms']:.3f} | {r['fps']:.0f} |")
    lines.append("")
    backend_note = ""
    for r in rows:
        if "backend=" in r["extra"]:
            backend_note = r["extra"]
            break
    lines.append(f"Tracker backend on this host: {backend_note}")
    lines.append("")
    lines.append(
        "Budget context: one camera at target_fps=10 needs one update every "
        "100ms; tracker cost must stay well under that alongside detection "
        "(see yolo_benchmark.md) and ReID.")
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tracker benchmark")
    parser.add_argument("--frames", type=int, default=100,
                        help="real-mode footage frames")
    parser.add_argument("--video", default="footage/cam1.mp4")
    parser.add_argument("--synthetic-boxes", nargs="+", type=int,
                        default=[5, 15, 30, 50])
    parser.add_argument("--synthetic-frames", type=int, default=200)
    args = parser.parse_args()

    video = Path(args.video)
    if not video.is_absolute():
        video = REPO_ROOT / video

    print(f"real pass ({args.frames} frames from {video.name}) ...")
    real = bench_real(video, args.frames)

    print("synthetic passes ...")
    synth = bench_synthetic(args.synthetic_boxes, args.synthetic_frames)

    write_report(real, synth, video, args.frames, args.synthetic_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
