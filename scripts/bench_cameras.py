#!/usr/bin/env python3
"""
Camera-count soak benchmark — MVP metrics row 5.

Mirrors the production edge topology (edge/run_all.py) on test hardware:
one shared DetectionService (YOLOv8n), one shared ReIDService, N
CameraWorkers at target_fps=10, ingesting from repo footage files (Docker/
mediamtx unavailable in this environment — RTSP transport overhead is NOT
included; GPU/queue/worker load is identical). Health posts go to a real
fusion server (uvicorn subprocess, fresh temp SQLite DB).

Per camera count K (default 1,2,3,4,6):
  - warmup (latency-guard deque fills), then a measurement window
  - poll GET /api/v1/cameras/health: detect_p95_ms, reduced_accuracy_mode,
    last_updated (-> achieved FPS from the health_post interval)
  - stop early for higher K if ALL cameras trip reduced_accuracy_mode
    for 3 consecutive polls (budget: DETECT_LATENCY_BUDGET_MS, default 100)

Writes docs/camera_soak_benchmark.md. Exit 0 after writing the report
(measurement tool, not a gate).

Usage:
    venv\\Scripts\\python.exe scripts\\bench_cameras.py
        [--counts 1 2 3 4 6] [--warmup 15] [--measure 60]
        [--target-fps 10] [--health-interval 30]
"""
import argparse
import json
import os
import statistics
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "camera_soak_benchmark.md"
FUSION_URL = "http://127.0.0.1:8000"
FOOTAGE = ["footage/cam1.mp4", "footage/cam2.mp4", "footage/cam3.mp4"]
BUDGET_MS = float(os.environ.get("DETECT_LATENCY_BUDGET_MS", "100"))


def gpu_temp() -> "float | None":
    """Sample GPU temperature (°C) via nvidia-smi; None if unavailable."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return float(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


def wait_fusion(timeout=45):
    import requests
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"{FUSION_URL}/health", timeout=2)
            if r.status_code == 200 and r.json().get("database") == "connected":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def start_fusion(db_path: Path, log_path: Path):
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["DETECT_LATENCY_BUDGET_MS"] = str(BUDGET_MS)
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "fusion_server.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO_ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    return proc, log


def parse_iso(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def poll_health(duration_s: float, interval_s: float, camera_ids):
    """Sample /api/v1/cameras/health for duration; return per-camera samples."""
    import requests
    samples = {cid: [] for cid in camera_ids}
    t_end = time.time() + duration_s
    while time.time() < t_end:
        try:
            r = requests.get(f"{FUSION_URL}/api/v1/cameras/health", timeout=2)
            data = r.json()
            now = time.time()
            for cid in camera_ids:
                h = data.get(cid)
                if h is None:
                    continue
                samples[cid].append({
                    "t": now,
                    "p95": h.get("detect_p95_ms"),
                    "reduced": bool(h.get("reduced_accuracy_mode")),
                    "last_updated": h.get("last_updated"),
                    "status": h.get("status"),
                })
        except Exception:
            pass
        time.sleep(interval_s)
    return samples


def achieved_fps(samples, health_interval: int) -> float:
    """Achieved processing FPS from deltas between health POSTs.

    The edge posts health once every `health_interval` frames, so
    fps = health_interval / median(post_delta)."""
    ts = [parse_iso(s["last_updated"]) for s in samples
          if s.get("last_updated")]
    if len(ts) < 3:
        return 0.0
    deltas = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    if not deltas:
        return 0.0
    return health_interval / statistics.median(deltas)


def run_soak(k: int, args) -> dict:
    import multiprocessing

    camera_ids = [f"k{k}-cam{i + 1}" for i in range(k)]
    urls = [str(REPO_ROOT / FOOTAGE[i % len(FOOTAGE)]) for i in range(k)]
    temp_start = gpu_temp()

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req_queue = multiprocessing.Queue()
    reid_res_queue = multiprocessing.Queue()

    from edge.detector import DetectionService
    detector = DetectionService(req_queue, res_queue)
    det_proc = multiprocessing.Process(target=detector.run, daemon=True)
    det_proc.start()

    from edge.reid_service import ReIDService
    reid = ReIDService(reid_req_queue, reid_res_queue,
                       model_path="models/osnet_ain_x1_0.onnx")
    reid_proc = multiprocessing.Process(target=reid.run, daemon=True)
    reid_proc.start()

    time.sleep(5)  # model load (mirrors run_all's settle)

    from edge.camera_worker import CameraWorker
    workers = []
    procs = []
    for cid, url in zip(camera_ids, urls):
        worker = CameraWorker(
            camera_url=url,
            camera_id=cid,
            fusion_url=FUSION_URL,
            req_queue=req_queue,
            res_queue=res_queue,
            reid_req_queue=reid_req_queue,
            reid_res_queue=reid_res_queue,
            target_fps=args.target_fps,
            display=False,
            force_mode="normal",  # isolate capacity; yolov8n_night.pt absent anyway
            mjpeg_port=8081,      # display off -> no HTTP server started
            health_check_interval=args.health_interval,
        )
        p = multiprocessing.Process(target=worker.run, daemon=True)
        p.start()
        workers.append(worker)
        procs.append(p)

    print(f"  K={k}: warmup {args.warmup}s ...")
    samples = poll_health(args.warmup, 2.0, camera_ids)  # discard warmup
    print(f"  K={k}: measuring {args.measure}s ...")
    samples = poll_health(args.measure, 3.0, camera_ids)

    # early-stop detection: all cameras reduced on last 3 consecutive polls
    trips = 0
    if samples and all(samples[c] for c in camera_ids):
        n_polls = min(len(samples[c]) for c in camera_ids)
        all_tripped_streak = 0
        for i in range(n_polls):
            if all(samples[c][i]["reduced"] for c in camera_ids):
                all_tripped_streak += 1
                if all_tripped_streak >= 3:
                    trips = 1
                    break
            else:
                all_tripped_streak = 0

    per_cam = {}
    for cid in camera_ids:
        s = samples[cid]
        p95s = [x["p95"] for x in s if x["p95"] is not None]
        per_cam[cid] = {
            "p95_max": max(p95s) if p95s else None,
            "p95_median": statistics.median(p95s) if p95s else None,
            "reduced_any": any(x["reduced"] for x in s),
            "reduced_end": s[-1]["reduced"] if s else None,
            "fps": achieved_fps(s, args.health_interval),
            "status": s[-1]["status"] if s else None,
            "polls": len(s),
        }

    all_reduced = all(c["reduced_end"] for c in per_cam.values() if c["reduced_end"] is not None) and \
                  all(c["reduced_any"] for c in per_cam.values())
    verdict = "degraded" if (all_reduced or trips) else "stable"

    # teardown
    temp_end = gpu_temp()
    for p in procs:
        p.terminate()
    try:
        req_queue.put(None)
        reid_req_queue.put(None)
    except Exception:
        pass
    det_proc.terminate()
    reid_proc.terminate()
    for p in procs + [det_proc, reid_proc]:
        p.join(timeout=5)
    time.sleep(2)

    return {"k": k, "cameras": per_cam, "verdict": verdict,
            "all_tripped_consecutive": bool(trips),
            "gpu_temp_start": temp_start, "gpu_temp_end": temp_end}


def write_report(results, args, early_stop_k):
    lines = [
        "# Camera Count Soak Benchmark (edge capacity)",
        "",
        "Measured with `scripts/bench_cameras.py` on test hardware (RTX 4050 "
        "laptop GPU), production edge topology: one shared DetectionService "
        "(YOLOv8n, CUDA via ultralytics auto-device), one shared ReIDService "
        "(OSNet + vehicle ReID, ONNX GPU), N CameraWorkers at "
        f"target_fps={args.target_fps}, force_mode=normal, face/plate "
        "disabled (run_all defaults).",
        "",
        "Ingest source: repo footage files (Docker daemon unavailable in this "
        "environment — RTSP transport overhead not included; GPU/queue/worker "
        "load identical to production). Health: real fusion server "
        f"(uvicorn, fresh temp SQLite), health POST every "
        f"{args.health_interval} frames; detect latency budget "
        f"{BUDGET_MS:.0f} ms (`DETECT_LATENCY_BUDGET_MS`), guard trips "
        "reduced_accuracy_mode after 3 consecutive over-budget p95 "
        "evaluations (production camera_worker logic).",
        "",
        f"Warmup {args.warmup}s (discarded), measure {args.measure}s per K, "
        f"cooldown {args.cooldown}s between K values (thermal settle). "
        "GPU temperature recorded at each K start/end (nvidia-smi).",
        "",
        "| K | Verdict | Per-camera detect p95 ms (max) | Achieved FPS "
        "(median) | Guard tripped | GPU C (start->end) |",
        "|---:|:---:|---|---:|:---:|:---:|",
    ]
    for r in results:
        p95s = [c["p95_max"] for c in r["cameras"].values()
                if c["p95_max"] is not None]
        p95_str = ", ".join(f"{p:.0f}" for p in p95s) if p95s else "n/a"
        fps_vals = [c["fps"] for c in r["cameras"].values() if c["fps"] > 0]
        fps_str = f"{statistics.median(fps_vals):.1f}" if fps_vals else "n/a"
        tripped = "yes" if (r["verdict"] == "degraded") else "no"
        t0, t1 = r.get("gpu_temp_start"), r.get("gpu_temp_end")
        temp_str = (f"{t0:.0f}->{t1:.0f}"
                    if t0 is not None and t1 is not None else "n/a")
        lines.append(f"| {r['k']} | {r['verdict']} | {p95_str} | {fps_str} | "
                     f"{tripped} | {temp_str} |")
    lines.append("")
    stable = [r["k"] for r in results if r["verdict"] == "stable"]
    max_stable = max(stable) if stable else 0
    if max_stable:
        lines.append(f"**Highest stable camera count at target_fps="
                     f"{args.target_fps} (all cameras within {BUDGET_MS:.0f} ms "
                     f"detect p95 budget, no reduced_accuracy_mode): "
                     f"K = {max_stable}**")
    else:
        lines.append("**No camera count stayed within budget.**")
    if early_stop_k:
        lines.append(f"(Measurement stopped at K={early_stop_k}: all cameras "
                     f"tripped the latency guard consecutively.)")
    lines.append("")
    lines.append("Per-camera detail:")
    lines.append("")
    lines.append("| K | Camera | p95 max ms | p95 median ms | FPS | "
                 "reduced (any) | status |")
    lines.append("|---:|---|---:|---:|---:|:---:|---|")
    for r in results:
        for cid, c in r["cameras"].items():
            p95max = f"{c['p95_max']:.0f}" if c["p95_max"] is not None else "n/a"
            p95med = (f"{c['p95_median']:.0f}"
                      if c["p95_median"] is not None else "n/a")
            lines.append(
                f"| {r['k']} | {cid} | {p95max} | {p95med} | "
                f"{c['fps']:.1f} | {'yes' if c['reduced_any'] else 'no'} | "
                f"{c['status'] or 'n/a'} |")
    lines.append("")
    lines.append(
        "Scope notes: footage ingest (no RTSP decode/network); face/plate "
        "sub-services off (run_all defaults); SQLite fusion DB. PRD target "
        "is 2-3 cameras — compare max_stable against that.")
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Camera-count soak")
    parser.add_argument("--counts", nargs="+", type=int, default=[1, 2, 3, 4, 6])
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--measure", type=int, default=60)
    parser.add_argument("--cooldown", type=int, default=30,
                        help="seconds to settle thermally between K values")
    parser.add_argument("--early-stop", action="store_true",
                        help="stop at first degraded K (default: run all Ks "
                             "for a complete capacity curve)")
    parser.add_argument("--target-fps", type=int, default=10)
    parser.add_argument("--health-interval", type=int, default=30)
    args = parser.parse_args()

    db_path = Path(tempfile.gettempdir()) / f"ibvap_bench_soak_{os.getpid()}.db"
    if db_path.exists():
        db_path.unlink()
    log_path = Path(tempfile.gettempdir()) / f"ibvap_bench_soak_{os.getpid()}.log"

    print("starting fusion server ...")
    fusion, flog = start_fusion(db_path, log_path)
    try:
        if not wait_fusion():
            print("[FAIL] fusion server did not come up")
            print(f"--- fusion log ---\n{log_path.read_text(encoding='utf-8')[-4000:]}")
            return 1
        print(f"fusion up (log: {log_path})")

        results = []
        early_stop_k = None
        for i, k in enumerate(args.counts):
            if i > 0 and args.cooldown > 0:
                print(f"cooldown {args.cooldown}s (thermal settle) ...")
                time.sleep(args.cooldown)
            print(f"=== soak K={k} ===")
            r = run_soak(k, args)
            results.append(r)
            print(f"  K={k}: verdict={r['verdict']} "
                  f"(gpu {r.get('gpu_temp_start')}->{r.get('gpu_temp_end')}C)")
            if (args.early_stop and r["verdict"] == "degraded"
                    and r["all_tripped_consecutive"]):
                # this K (and anything higher) is over capacity — stop
                remaining = [x for x in args.counts if x > k]
                if remaining:
                    early_stop_k = k
                    break

        write_report(results, args, early_stop_k)
        return 0
    finally:
        fusion.terminate()
        try:
            fusion.wait(timeout=10)
        except subprocess.TimeoutExpired:
            fusion.kill()
        flog.close()
        for p in (db_path, log_path):
            try:
                p.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
