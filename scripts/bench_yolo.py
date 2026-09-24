#!/usr/bin/env python3
"""
Benchmark YOLO detector variants (v8n vs v8m) on repo footage.

Measures end-to-end FPS and latency per model on GPU (if torch+CUDA
available) and/or CPU over footage/cam1.mp4. Writes/updates
docs/yolo_benchmark.md with the measured table.

Usage:
    python scripts/bench_yolo.py [--models yolov8n.pt yolov8m.pt]
                                 [--video footage/cam1.mp4] [--frames 100]
                                 [--imgsz 640] [--device auto|cpu|cuda]
Exit code 0 after writing the report regardless of FPS (this is a
measurement tool, not a gate).
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "yolo_benchmark.md"


def pick_device(requested: str) -> str:
    import torch
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        print("[WARN] cuda requested but torch has no CUDA build — falling back to cpu")
        return "cpu"
    return requested


def bench_model(weights: str, frames, imgsz: int, device: str) -> dict:
    import torch
    from ultralytics import YOLO

    model = YOLO(weights)
    # Move to device (ultralytics .to works for torch models)
    model.to(device)
    # Warmup
    dummy = torch.zeros(1, 3, imgsz, imgsz)
    for _ in range(3):
        model.predict(dummy, imgsz=imgsz, device=device, verbose=False)

    latencies = []
    for i in range(len(frames)):
        t0 = time.perf_counter()
        model.predict(frames[i], imgsz=imgsz, device=device, verbose=False)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    latencies.sort()
    mean = statistics.mean(latencies)
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    return {
        "weights": weights,
        "device": device,
        "n_frames": len(frames),
        "mean_ms": mean,
        "p50_ms": statistics.median(latencies),
        "p95_ms": p95,
        "fps": 1000.0 / mean if mean > 0 else 0.0,
    }


def load_frames(video_path: Path, max_frames: int):
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(video_path)
    frames = []
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames decoded from {video_path}")
    return frames


def write_report(results: list, video: Path, imgsz: int, device: str):
    lines = [
        "# YOLO Detector Benchmark (v8n vs v8m)",
        "",
        "Measured with `scripts/bench_yolo.py` on repo footage "
        f"(`{video.relative_to(REPO_ROOT).as_posix() if video.is_relative_to(REPO_ROOT) else video}`), "
        f"imgsz={imgsz}, device={device}.",
        "",
        "| Model | Device | Frames | Mean ms | p50 ms | p95 ms | FPS |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['weights']} | {r['device']} | {r['n_frames']} | "
            f"{r['mean_ms']:.1f} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} | "
            f"{r['fps']:.1f} |")
    lines.append("")
    lines.append(
        "Real-time budget: >= 25 FPS end-to-end per camera counts as "
        "real-time for this project's edge tier.")
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Merge with any existing table so a CPU run does not clobber GPU rows
    # (and vice versa): keep rows from prior runs whose (model, device) pair
    # is not in this run's results.
    new_keys = {(r["weights"], r["device"]) for r in results}
    kept_rows = []
    if REPORT_PATH.exists():
        for row in REPORT_PATH.read_text(encoding="utf-8").splitlines():
            if not row.startswith("| ") or row.startswith("| Model") or row.startswith("|---"):
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) >= 7 and (cells[0], cells[1]) not in new_keys:
                kept_rows.append(row)
    all_rows = kept_rows + [
        f"| {r['weights']} | {r['device']} | {r['n_frames']} | "
        f"{r['mean_ms']:.1f} | {r['p50_ms']:.1f} | {r['p95_ms']:.1f} | "
        f"{r['fps']:.1f} |"
        for r in results
    ]
    header = [
        "# YOLO Detector Benchmark (v8n vs v8m)",
        "",
        "Measured with `scripts/bench_yolo.py` on repo footage "
        f"(`{video.relative_to(REPO_ROOT).as_posix() if video.is_relative_to(REPO_ROOT) else video}`), "
        "imgsz=640. Re-run per device; rows merge by (model, device).",
        "",
        "| Model | Device | Frames | Mean ms | p50 ms | p95 ms | FPS |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    REPORT_PATH.write_text(
        "\n".join(header + all_rows) + "\n\n" +
        "Real-time budget: >= 25 FPS end-to-end per camera counts as "
        "real-time for this project's edge tier.\n",
        encoding="utf-8")
    print(f"report written: {REPORT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="YOLO v8n vs v8m benchmark")
    parser.add_argument("--models", nargs="+", default=["yolov8n.pt", "yolov8m.pt"])
    parser.add_argument("--video", default="footage/cam1.mp4")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()

    video = Path(args.video)
    if not video.is_absolute():
        video = REPO_ROOT / video
    device = pick_device(args.device)
    import torch
    print(f"device={device} torch={torch.__version__}")

    frames = load_frames(video, args.frames)
    print(f"loaded {len(frames)} frames from {video.name}")

    results = []
    for weights in args.models:
        print(f"benchmarking {weights} on {device} ...")
        r = bench_model(weights, frames, args.imgsz, device)
        results.append(r)
        print(f"  {weights}: {r['fps']:.1f} FPS "
              f"(mean={r['mean_ms']:.1f}ms p95={r['p95_ms']:.1f}ms)")

    write_report(results, video, args.imgsz, device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
