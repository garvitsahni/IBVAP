#!/usr/bin/env python
"""Car recall + plate read-rate eval on captured webcam frames (Phase 1.3).

Usage:
    venv\\Scripts\\python.exe scripts/eval_car_recall.py --dir debug/car-miss \\
        --model yolov8n.pt --imgsz 640 [--labels labels.json]

labels.json (optional): {"<frame_stem>": true/false} (car visible?).
Without labels, reports detection-rate + top-conf stats (no recall).

Plate leg: for every frame with a car box @>=0.25, runs _read_plate and
reports read-rate (>=4 chars). Needs EasyOCR + plate model; degrades to
"OCR unavailable" when absent.
"""
import argparse
import glob
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="dir with frame_*.jpg (+ frame_*.json meta)")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--conf-levels", default="0.10,0.25,0.50")
    ap.add_argument("--pattern", default="frame_*.jpg")
    ap.add_argument("--plate-conf", type=float, default=0.25)
    args = ap.parse_args()

    from ultralytics import YOLO
    model = YOLO(args.model if os.path.isabs(args.model)
                 else os.path.join(REPO_ROOT, args.model))

    labels = {}
    if args.labels:
        labels = json.load(open(args.labels, encoding="utf-8-sig"))
        print(f"labels: {len(labels)} frames")

    try:
        from fusion_server.api.routes.detect import _read_plate
        import cv2 as cv2_mod
        ocr_ok = _read_plate is not None
    except Exception as e:
        print(f"plate leg disabled (import failed: {e})")
        _read_plate = None
        ocr_ok = False

    import cv2
    conf_levels = [float(x) for x in args.conf_levels.split(",")]
    paths = sorted(glob.glob(os.path.join(args.dir, args.pattern)))
    print(f"frames: {len(paths)} | model={args.model} imgsz={args.imgsz}")

    per_frame = []
    lat = []
    plate_attempts = 0
    plate_reads = 0
    for p in paths:
        frame = cv2.imread(p)
        if frame is None:
            continue
        t0 = time.perf_counter()
        res = model(frame, classes=[2], verbose=False, imgsz=args.imgsz)[0]
        lat.append((time.perf_counter() - t0) * 1000)
        cars = []
        if res.boxes is not None:
            for box in res.boxes:
                cars.append({
                    "conf": float(box.conf[0]),
                    "bbox": [float(v) for v in box.xyxy[0].tolist()],
                })
        cars.sort(key=lambda c: -c["conf"])
        top = cars[0]["conf"] if cars else 0.0
        stem = os.path.splitext(os.path.basename(p))[0]
        rec = {"frame": stem, "n_car": len(cars), "top_conf": round(top, 4),
               "has_car": labels.get(stem)}
        # Plate leg on found cars only
        if ocr_ok and cars and cars[0]["conf"] >= args.plate_conf:
            x1, y1, x2, y2 = cars[0]["bbox"]
            try:
                text = _read_plate(frame, x1, y1, x2, y2)
            except Exception:
                text = None
            plate_attempts += 1
            if text and len(text) >= 4:
                plate_reads += 1
                rec["plate_text"] = text
        per_frame.append(rec)

    lat.sort()
    p50 = lat[len(lat) // 2] if lat else 0
    print(f"latency ms: p50={p50:.0f} n={len(lat)}")
    det_rate = sum(1 for r in per_frame if r["n_car"] > 0) / max(1, len(per_frame))
    mean_top = sum(r["top_conf"] for r in per_frame) / max(1, len(per_frame))
    print(f"car detection-rate(any conf): {det_rate:.3f} | mean top-car-conf: {mean_top:.3f}")
    for cl in conf_levels:
        hit = sum(1 for r in per_frame if r["top_conf"] >= cl)
        print(f"  @ conf>={cl:.2f}: {hit}/{len(per_frame)} frames with car box")
    lab = [r for r in per_frame if r.get("has_car") is True]
    if lab:
        for cl in conf_levels:
            rec = sum(1 for r in lab if r["top_conf"] >= cl) / len(lab)
            print(f"  RECALL @ conf>={cl:.2f} (n={len(lab)} labeled positive): {rec:.3f}")
    else:
        print("  recall: no positive labels — detection-rate only")
    if plate_attempts:
        print(f"plate read-rate on found cars: {plate_reads}/{plate_attempts} = "
              f"{plate_reads / plate_attempts:.3f}")
    elif ocr_ok:
        print("plate read-rate: no found cars to attempt OCR on")
    out = os.path.join(args.dir, f"eval_{os.path.splitext(os.path.basename(args.model))[0]}_"
                                 f"{args.imgsz}.json")
    json.dump({"model": args.model, "imgsz": args.imgsz, "p50_ms": round(p50, 1),
               "frames": per_frame}, open(out, "w"), indent=1)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
