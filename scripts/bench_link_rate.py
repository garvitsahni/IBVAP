#!/usr/bin/env python3
"""
Live cross-camera link-rate benchmark — MVP metrics row 3b (gated model
metrics from tests/test_eval_gates.py cover row 3a; this measures whether the
PRODUCTION matching path actually links identities across cameras).

Method (real, not simulated):
  - K VeRi-776 identity pairs with ground truth: same vehicle id, two
    different cameras
  - both images embedded with the production vehicle ReID path
    (ReIDService.extract_embedding, is_vehicle=True -> vehicle_reid.onnx,
    ImageNet-normalized 256x256)
  - pair ingested through the production _ingest_event() on a fresh temp
    SQLite DB: event A (cam X, time T), event B (cam Y, T+4min — inside the
    MatchingEngine's 5-minute window); pairs spaced 10 min apart so each
    pair's window contains only its own two events
  - linked := B received the same object_id as A (threshold 0.60 cosine,
    vehicle — engine defaults)

Deviation from the original footage-walk-through plan (flagged to owner):
repo footage has no verified cross-camera identity ground truth, so a
footage-based success % would be unverifiable; VeRi provides real
cross-camera ground truth through the same production code path.

Writes docs/link_rate_benchmark.md. Exit 0 after writing the report.

Usage:
    venv\\Scripts\\python.exe scripts\\bench_link_rate.py [--pairs 20]
"""
import argparse
import os
import random
import statistics
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "docs" / "link_rate_benchmark.md"

VERI_ROOT = REPO_ROOT / "data" / "eval" / "veri-776" / "VeRi"
VEHICLE_MODEL = REPO_ROOT / "models" / "vehicle_reid.onnx"


def parse_veri_name(fname: str):
    parts = Path(fname).stem.split("_")
    return parts[0], parts[1]


def collect_pairs(need: int, seed: int = 42):
    """Identities with images from >=2 cameras -> list of (id, fileA, fileB)."""
    by_id = defaultdict(dict)  # id -> {cam: path}
    for split in ("image_query", "image_test"):
        d = VERI_ROOT / split
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.jpg")):
            vid, cam = parse_veri_name(f.name)
            if cam not in by_id[vid]:
                by_id[vid][cam] = f

    candidates = [(vid, cams) for vid, cams in sorted(by_id.items())
                  if len(cams) >= 2]
    rng = random.Random(seed)
    rng.shuffle(candidates)
    pairs = []
    for vid, cams in candidates:
        if len(pairs) >= need:
            break
        cams_sorted = sorted(cams)
        file_a = by_id[vid][cams_sorted[0]]
        file_b = by_id[vid][cams_sorted[1]]
        pairs.append((vid, cams_sorted[0], cams_sorted[1], file_a, file_b))
    return pairs


def embed_vehicle(reid, path: Path):
    import cv2
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    emb = reid.extract_embedding(img, is_vehicle=True)
    if emb is None:
        raise RuntimeError(f"embedding failed for {path}")
    return emb


def main() -> int:
    parser = argparse.ArgumentParser(description="Live cross-camera link rate")
    parser.add_argument("--pairs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not VEHICLE_MODEL.is_file():
        print(f"[FAIL] missing {VEHICLE_MODEL}")
        return 1
    if not VERI_ROOT.is_dir():
        print(f"[FAIL] missing {VERI_ROOT}")
        return 1

    db_path = Path(tempfile.gettempdir()) / f"ibvap_bench_link_{os.getpid()}.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    import numpy as np

    import fusion_server.db.models  # noqa: F401
    import fusion_server.db.models_roi  # noqa: F401
    from fusion_server.db.session import init_db, SessionLocal
    from fusion_server.api.events import DetectionEventCreate, BBox, _ingest_event
    from fusion_server.services.cooldown_gate import get_cooldown_gate
    from edge.reid_service import ReIDService

    print("collecting VeRi cross-camera pairs ...")
    pairs = collect_pairs(args.pairs, args.seed)
    if len(pairs) < args.pairs:
        print(f"[WARN] only {len(pairs)} identities with >=2 cameras "
              f"(wanted {args.pairs})")
    if not pairs:
        print("[FAIL] no cross-camera pairs found")
        return 1

    print("loading production vehicle ReID ...")
    reid = ReIDService(None, None)
    reid._load_vehicle_model()
    if reid._vehicle_session is None:
        print("[FAIL] vehicle ReID model failed to load")
        return 1

    init_db()
    get_cooldown_gate().reset()

    db = SessionLocal()
    linked = 0
    cosines = []
    rows = []
    base = datetime(2026, 1, 1, 8, 0, 0)
    try:
        for i, (vid, cam_a, cam_b, fa, fb) in enumerate(pairs):
            emb_a = embed_vehicle(reid, fa)
            emb_b = embed_vehicle(reid, fb)
            cos = float(np.dot(emb_a, emb_b))  # both unit vectors
            cosines.append(cos)

            t_a = base + timedelta(minutes=10 * i)
            t_b = t_a + timedelta(minutes=4)  # inside MatchingEngine 5-min window

            ev_a = DetectionEventCreate(
                camera_id=f"vcam-{cam_a}",
                timestamp=t_a,
                object_type="vehicle",
                track_id=f"{vid}-a",
                bbox=BBox(x1=0.1, y1=0.1, x2=0.9, y2=0.9),
                embedding=emb_a.tolist(),
                confidence=0.9,
            )
            res_a = _ingest_event(ev_a, db)
            obj_a = res_a["object_id"]

            ev_b = DetectionEventCreate(
                camera_id=f"vcam-{cam_b}",
                timestamp=t_b,
                object_type="vehicle",
                track_id=f"{vid}-b",
                bbox=BBox(x1=0.1, y1=0.1, x2=0.9, y2=0.9),
                embedding=emb_b.tolist(),
                confidence=0.9,
            )
            res_b = _ingest_event(ev_b, db)
            obj_b = res_b["object_id"]

            ok = obj_a is not None and obj_a == obj_b
            if ok:
                linked += 1
            rows.append((vid, cam_a, cam_b, cos, ok))
            print(f"  pair {i + 1}/{len(pairs)} id={vid} {cam_a}->{cam_b} "
                  f"cos={cos:.3f} linked={'yes' if ok else 'NO'}")
    finally:
        db.close()

    n = len(pairs)
    rate = 100.0 * linked / n if n else 0.0
    above_thr = sum(1 for c in cosines if c >= 0.60)
    print(f"link rate: {linked}/{n} = {rate:.1f}% "
          f"(cos>=0.60: {above_thr}/{n}, "
          f"mean cos={statistics.mean(cosines):.3f})")

    lines = [
        "# Live Cross-Camera Link Rate (production matching path)",
        "",
        "Measured with `scripts/bench_link_rate.py`: K VeRi-776 identity pairs "
        "(same vehicle, two different cameras) embedded with the production "
        "vehicle ReID path (`ReIDService.extract_embedding` -> "
        "`vehicle_reid.onnx`) and ingested through the production "
        "`_ingest_event()` + `MatchingEngine` (vehicle threshold 0.60 cosine, "
        "5-minute window; event B at T+4min, pairs spaced 10 min apart so "
        "each window contains only its own pair).",
        "",
        "**Deviation from plan (flagged):** the original plan proposed "
        "cam1->cam2 footage walk-throughs, but repo footage has no verified "
        "cross-camera identity ground truth — a footage success % would be "
        "unverifiable. VeRi provides real cross-camera ground truth through "
        "the same production code path.",
        "",
        f"## Result: {linked}/{n} linked = **{rate:.1f}%**",
        "",
        f"- pairs with cosine >= 0.60 threshold: {above_thr}/{n}",
        f"- mean same-id cross-camera cosine: {statistics.mean(cosines):.3f}",
        "",
        "| Vehicle ID | Cam A | Cam B | Cosine | Linked |",
        "|---|---|---|---:|:---:|",
    ]
    for vid, cam_a, cam_b, cos, ok in rows:
        lines.append(f"| {vid} | {cam_a} | {cam_b} | {cos:.3f} | "
                     f"{'yes' if ok else 'NO'} |")
    lines.append("")
    lines.append(
        "Scope notes: K=20 pairs (default); detection-box quality is not "
        "tested here (full-image crops, as VeRi images are vehicle crops) — "
        "end-to-end with detector noise is bounded by this + the gated "
        "Rank-1 metric in tests/test_eval_gates.py. Single-process SQLite.")
    lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {REPORT_PATH}")

    try:
        db_path.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
