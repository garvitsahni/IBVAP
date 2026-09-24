#!/usr/bin/env python
"""Fine-tune YOLOv8s as the webcam car/bike detector (Phase 3.2).

Builds data/car-bike-ft/{train,val} from the hand-labeled pool
(data/car-bike-train/pool + labels/, local ids 0=car 1=motorcycle remapped
to COCO 2/3, 80-class head preserved so downstream class ids never change),
mixes in COCO128 as anti-forgetting data, holds out 15%% for the gate test.

Run: venv\\Scripts\\python.exe scripts/train_car_detector.py [--epochs 100]
Overnight, detached: run with output redirected to a log file.

Outputs: models/car-finetune-v1/weights/{best,last}.pt + data.yaml +
val_files.txt manifest. Nothing is committed (weights + data are gitignored).
"""
import argparse
import glob
import os
import random
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Local label id -> COCO id (keep the 80-class head, preserve downstream ids).
# Ids already in COCO space (2/3, e.g. verified pseudo-labels) pass through.
REMAP = {0: 2, 1: 3}

COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]


def labeled_stems(pool, labels):
    # Frames WITH a label file count — including empty ones, which train as
    # explicit background negatives (verified-empty dark frames).
    stems = []
    for img in glob.glob(os.path.join(pool, "*.jpg")):
        stem = os.path.splitext(os.path.basename(img))[0]
        if os.path.exists(os.path.join(labels, stem + ".txt")):
            stems.append(stem)
    return sorted(stems)


def has_bike(labels, stem):
    for line in open(os.path.join(labels, stem + ".txt"), encoding="utf-8-sig"):
        if line.strip().split(" ")[0] == "1":
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--no-coco128", action="store_true",
                    help="skip COCO128 anti-forgetting mix")
    ap.add_argument("--dry-run", action="store_true",
                    help="build dataset only, do not train")
    args = ap.parse_args()

    pool = os.path.join(REPO_ROOT, "data", "car-bike-train", "pool")
    labels = os.path.join(REPO_ROOT, "data", "car-bike-train", "labels")
    ft = os.path.join(REPO_ROOT, "data", "car-bike-ft")
    if os.path.exists(ft):
        shutil.rmtree(ft)

    stems = labeled_stems(pool, labels)
    print(f"labeled frames: {len(stems)}")
    if len(stems) < 20:
        print("REFUSING: fewer than 20 labeled frames — collect more first")
        return 2
    rng = random.Random(args.seed)
    bike = [s for s in stems if has_bike(labels, s)]
    car = [s for s in stems if s not in set(bike)]
    rng.shuffle(bike)
    rng.shuffle(car)
    nvb = max(1, round(len(bike) * args.val_frac))
    nvc = max(1, round(len(car) * args.val_frac))
    val = set(bike[:nvb] + car[:nvc])
    train = [s for s in stems if s not in val]
    print(f"train={len(train)} (car={len([s for s in train if s in car])}, "
          f"bike={len([s for s in train if s in bike])}) val={len(val)}")

    for split, names in (("train", train), ("val", val)):
        os.makedirs(os.path.join(ft, split, "images"), exist_ok=True)
        os.makedirs(os.path.join(ft, split, "labels"), exist_ok=True)
        for s in names:
            shutil.copy(os.path.join(pool, s + ".jpg"),
                        os.path.join(ft, split, "images", s + ".jpg"))
            out = []
            for line in open(os.path.join(labels, s + ".txt"), encoding="utf-8-sig"):
                p = line.strip().split(" ")
                if not p or not p[0]:
                    continue
                cid = int(p[0])
                out.append(" ".join([str(REMAP.get(cid, cid))] + p[1:]))
            open(os.path.join(ft, split, "labels", s + ".txt"), "w").write("\n".join(out) + "\n")
    open(os.path.join(ft, "val_files.txt"), "w").write("\n".join(sorted(val)) + "\n")

    # COCO128 anti-forgetting mix (val stays pure user frames).
    # check_det_dataset downloads coco128 on first use (~100MB).
    if not args.no_coco128:
        try:
            from ultralytics.data.utils import check_det_dataset
            check_det_dataset("coco128.yaml")  # ensures datasets/coco128 exists
            ds = os.path.join(REPO_ROOT, "datasets", "coco128")
            imgs = sorted(glob.glob(os.path.join(ds, "images", "train2017", "*.jpg")))
            labs = os.path.join(ds, "labels", "train2017")
            n = 0
            for ip in imgs:
                stem = os.path.splitext(os.path.basename(ip))[0]
                lp = os.path.join(labs, stem + ".txt")
                if not os.path.exists(lp):
                    continue
                shutil.copy(ip, os.path.join(ft, "train", "images", "coco128_" + stem + ".jpg"))
                shutil.copy(lp, os.path.join(ft, "train", "labels", "coco128_" + stem + ".txt"))
                n += 1
            print(f"coco128 mixed into train: {n} images")
        except Exception as e:
            print(f"COCO128 unavailable ({e}) — training on user frames only")

    yaml_text = ("path: %s\ntrain: train/images\nval: val/images\nnc: 80\nnames:\n" % ft.replace("\\", "/"))
    for i, name in enumerate(COCO80):
        yaml_text += f"  {i}: {name}\n"
    data_yaml = os.path.join(ft, "data.yaml")
    open(data_yaml, "w").write(yaml_text)
    print(f"wrote {data_yaml}")

    if args.dry_run:
        return 0

    from ultralytics import YOLO
    model = YOLO(os.path.join(REPO_ROOT, "yolov8s.pt"))
    model.train(
        data=data_yaml,
        epochs=args.epochs,
        patience=25,
        batch=args.batch,
        imgsz=640,
        freeze=10,          # keep COCO backbone fixed for the first 10 epochs
        lr0=0.001,          # gentle fine-tune LR (default 0.01 is for scratch)
        device=0,
        workers=0,          # Windows-safe dataloader
        seed=args.seed,
        project=os.path.join(REPO_ROOT, "models", "car-finetune-v1"),
        name="train",
        exist_ok=True,
        verbose=True,
    )
    print("done — best weights: models/car-finetune-v1/train/weights/best.pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
