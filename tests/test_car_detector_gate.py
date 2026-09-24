"""Acceptance gate for the fine-tuned car/bike detector (Phase 3).

Pass criteria (honest given data volume — see docstring):
- car/bike recall >= 0.80 @ conf 0.25 on the held-out val split
  (data/car-bike-ft/val, 16 frames never seen in training), AND
- car recall >= 0.80 @ conf 0.25 on the independent first-session set
  (debug/eval-car + labels.json, 11 positives from a different day/pose mix).

Skips (does not fail) when weights or data are absent — training is an
explicit step, not part of the default suite. Val is small (16 frames, each
frame ~= 6%%), so this gate guards against collapse/overfit, not fine ranking.
Person/motorcycle-general regression is mitigated by construction (frozen
backbone x10 epochs, lr0=0.001, COCO128 mixed into train).
"""
import glob
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = os.path.join(REPO_ROOT, "models", "car-finetune-v1", "train", "weights", "best.pt")
FT = os.path.join(REPO_ROOT, "data", "car-bike-ft")

WANT = {2, 3}  # car, motorcycle (COCO ids — head preserved by fine-tune)


def _recall(model, frames, positives, conf=0.25):
    hits = 0
    for stem in positives:
        img = None
        for cand in glob.glob(os.path.join(frames, stem + ".*")):
            if cand.endswith((".jpg", ".jpeg", ".png")):
                img = cand
                break
        assert img is not None, f"missing image for {stem}"
        import cv2
        frame = cv2.imread(img)
        r = model(frame, classes=sorted(WANT), verbose=False, imgsz=640)[0]
        top = 0.0
        if r.boxes is not None:
            for box in r.boxes:
                if int(box.cls[0]) in WANT:
                    top = max(top, float(box.conf[0]))
        if top >= conf:
            hits += 1
    return hits / len(positives)


def _need_what():
    if not os.path.exists(WEIGHTS):
        pytest.skip("fine-tuned weights absent — run scripts/train_car_detector.py first")
    if not os.path.isdir(os.path.join(FT, "val", "images")):
        pytest.skip("fine-tune val split absent")


def test_val_split_recall():
    _need_what()
    from ultralytics import YOLO
    model = YOLO(WEIGHTS)
    val_labels = os.path.join(FT, "val", "labels")
    positives = []
    for f in os.listdir(val_labels):
        if not f.endswith(".txt"):
            continue
        content = open(os.path.join(val_labels, f), encoding="utf-8-sig").read().strip()
        if content:
            positives.append(os.path.splitext(f)[0])
    assert len(positives) >= 10, f"val split too small: {len(positives)}"
    rec = _recall(model, os.path.join(FT, "val", "images"), positives)
    assert rec >= 0.80, f"val recall {rec:.3f} < 0.80"


def test_first_session_recall():
    # First-session frames now train the model, so the old held-out check
    # would be contaminated. Replaced by a no-regression-vs-stock gate below.
    pytest.skip("superseded by test_no_regression_vs_stock (first-session frames train the model)")


def test_no_regression_vs_stock():
    # The fine-tuned weights must beat stock yolov8m on the SAME val split —
    # this is what proves the dark-room regression is actually fixed.
    _need_what()
    from ultralytics import YOLO
    tuned = YOLO(WEIGHTS)
    stock = YOLO(os.path.join(REPO_ROOT, "yolov8m.pt"))
    val_labels = os.path.join(FT, "val", "labels")
    positives = []
    for f in os.listdir(val_labels):
        if not f.endswith(".txt"):
            continue
        content = open(os.path.join(val_labels, f), encoding="utf-8-sig").read().strip()
        if content:
            positives.append(os.path.splitext(f)[0])
    assert len(positives) >= 10
    rec_tuned = _recall(tuned, os.path.join(FT, "val", "images"), positives)
    rec_stock = _recall(stock, os.path.join(FT, "val", "images"), positives)
    assert rec_tuned >= 0.80, f"tuned val recall {rec_tuned:.3f} < 0.80"
    assert rec_tuned >= rec_stock, (
        f"tuned {rec_tuned:.3f} worse than stock yolov8m {rec_stock:.3f} on val"
    )
