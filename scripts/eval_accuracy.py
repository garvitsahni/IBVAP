#!/usr/bin/env python3
"""
Accuracy evaluation for IBVAP Re-ID models on the repo's own footage.

Method (no external data needed):
- Sample frames from footage/cam1.mp4 + cam2.mp4, detect persons (YOLOv8n),
  link detections across time into tracks by greedy IoU matching.
- Embed crops with the ONNX Re-ID model under test (via edge/model_runtime).
- temporal: mean cosine between same-track crops >= 2s apart (same identity).
- cross:    mean cosine between different-track crops (different identities).
- Gate: temporal >= 0.70 and (temporal - cross) >= 0.15.

Usage:
    python scripts/eval_accuracy.py --person-footage [--model models/x.onnx]
                                    [--frames 25] [--videos footage/cam1.mp4 ...]

Exit code 0 only if gates pass.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

GATE_TEMPORAL = 0.70
GATE_MARGIN = 0.15
GATE_VEHICLE_RANK1 = 0.60
GATE_PLATE_PRECISION = 0.85
GATE_FACE_RANK1 = 0.90

# LFW funneled archive (scikit-learn's citable mirror of the original
# vis-www.cs.umass.edu dataset; sha256 verified before extract).
LFW_URL = "https://ndownloader.figshare.com/files/5976015"
LFW_SHA256 = "b47c8422c8cded889dc5a13418c4bc2abbda121092b3533a83306f90d900100a"


def ensure_lfw(data_dir=None):
    """Download + extract LFW funneled once into data/eval/lfw_funneled/."""
    import hashlib
    import tarfile
    import urllib.request

    root = Path(data_dir) if data_dir else REPO_ROOT / "data" / "eval"
    images_dir = root / "lfw_funneled"
    if images_dir.is_dir() and any(images_dir.iterdir()):
        return images_dir
    root.mkdir(parents=True, exist_ok=True)
    tgz = root / "lfw-funneled.tgz"
    if not tgz.exists():
        print(f"  downloading LFW funneled from {LFW_URL} ...", flush=True)
        urllib.request.urlretrieve(LFW_URL, tgz)
    sha = hashlib.sha256(tgz.read_bytes()).hexdigest()
    if sha != LFW_SHA256:
        tgz.unlink(missing_ok=True)
        raise RuntimeError(f"LFW archive sha256 mismatch: {sha}")
    print("  extracting LFW ...", flush=True)
    with tarfile.open(tgz, "r:gz") as tf:
        tf.extractall(path=root)
    tgz.unlink()
    return images_dir


def eval_face_rank1(model_path, lfw_dir, max_identities=200):
    """Rank-1 identification on LFW identities with >=2 images.

    Production-faithful path: FaceDetectorService.detect_faces (buffalo_l
    det) picks the largest face in the image, its bbox is cropped exactly as
    camera_worker does, and the crop is embedded through
    FaceEmbeddingService ([-1,1] preprocess + unit-normalize). Images where
    detection fails count as misses (production would produce no embedding).

    Protocol: per sampled identity, image #1 is the gallery entry, image #2
    is the query; distractors are every other sampled identity's gallery
    image. Rank-1 = queries whose cosine argmax is the own identity.
    """
    import cv2
    import numpy as np
    from edge.face_detector import FaceDetectorService
    from edge.face_embedding import FaceEmbeddingService

    lfw_dir = Path(lfw_dir)
    ids = []
    for d in sorted(p for p in lfw_dir.iterdir() if p.is_dir()):
        imgs = sorted(d.glob("*.jpg"))
        if len(imgs) >= 2:
            ids.append((d.name, imgs[0], imgs[1]))
    if len(ids) < 2:
        raise RuntimeError(f"not enough LFW identities with >=2 images in {lfw_dir}")
    if max_identities and len(ids) > max_identities:
        # deterministic even sample across the alphabet
        step = len(ids) / max_identities
        ids = [ids[int(i * step)] for i in range(max_identities)]

    det = FaceDetectorService(None, None)
    det._load_model()
    assert det._app is not None, "face detector (insightface buffalo_l) failed to load"
    emb_svc = FaceEmbeddingService(None, None, model_path=str(model_path))
    emb_svc._load_model()
    assert emb_svc._session is not None, f"failed to load {model_path}"

    def embed_lfw(path):
        img = cv2.imread(str(path))
        if img is None:
            raise RuntimeError(f"failed to read LFW image {path}")
        faces = det.detect_faces(img)
        if not faces:
            return None  # production would emit no embedding
        x1, y1, x2, y2 = max(faces, key=lambda f: (f["bbox"][2] - f["bbox"][0])
                                                     * (f["bbox"][3] - f["bbox"][1]))["bbox"]
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return emb_svc.extract_embedding(img[y1:y2, x1:x2])

    galleries, queries = [], []
    det_failures = 0
    for _, gpath, qpath in ids:
        g = embed_lfw(gpath)
        q = embed_lfw(qpath)
        det_failures += (g is None) + (q is None)
        galleries.append(g)
        queries.append(q)

    dim = next(e.size for e in galleries + queries if e is not None)
    G = np.stack([e if e is not None else np.zeros(dim) for e in galleries])
    Q = np.stack([e if e is not None else np.zeros(dim) for e in queries])
    sims = Q @ G.T
    # no-embedding queries are misses; no-embedding galleries never win unless
    # all sims <= 0 (zero vector) — argmax on zero rows is deterministic index 0,
    # so mask those rows to -inf and count them as misses explicitly.
    hits = 0
    for qi in range(len(ids)):
        if queries[qi] is None:
            continue
        masked = sims[qi].copy()
        for gi, e in enumerate(galleries):
            if e is None:
                masked[gi] = -np.inf
        if int(np.argmax(masked)) == qi and galleries[qi] is not None:
            hits += 1
    return {"rank1": hits / len(ids), "hits": hits, "n_identities": len(ids),
            "det_failures": det_failures}


def eval_plate_detector(model_path, plates_dir, max_images=None, iou_thr=0.5):
    """Precision @ IoU 0.5 for the production PlateDetectorService.

    Runs edge.plate_detector.PlateDetectorService.detect_plates end-to-end
    (same preprocess/parse/NMS/threshold as production) on the keremberke
    license-plate test split (COCO bboxes in original image pixels).
    Precision = matched predictions / total predictions (greedy 1-1).
    """
    import json
    import cv2
    import multiprocessing
    from edge.plate_detector import PlateDetectorService

    plates_dir = Path(plates_dir)
    with open(plates_dir / "_annotations.coco.json", encoding="utf-8") as f:
        coco = json.load(f)
    gts: dict[int, list] = {}
    for ann in coco["annotations"]:
        x, y, w, h = ann["bbox"]
        gts.setdefault(ann["image_id"], []).append(
            [x, y, x + w, y + h])
    images = coco["images"]
    if max_images:
        images = images[:max_images]

    q = multiprocessing.Queue()
    svc = PlateDetectorService(q, q, model_path=str(model_path))
    svc._load_model()
    assert svc._session is not None, f"failed to load {model_path}"

    tp = 0
    n_preds = 0
    for info in images:
        img = cv2.imread(str(plates_dir / info["file_name"]))
        if img is None:
            continue
        preds = svc.detect_plates(img)
        gt_boxes = gts.get(info["id"], [])
        matched = set()
        for p in preds:
            n_preds += 1
            for gi, g in enumerate(gt_boxes):
                if gi in matched:
                    continue
                if iou(p["bbox"], g) >= iou_thr:
                    tp += 1
                    matched.add(gi)
                    break
    precision = tp / n_preds if n_preds else 0.0
    return {"precision": precision, "tp": tp, "n_preds": n_preds,
            "n_images": len(images)}


def parse_veri_name(fname):
    """VeRi-776 names look like 0002_c002_00030600_0.jpg -> (id, cam)."""
    base = Path(fname).stem
    parts = base.split("_")
    return parts[0], parts[1]


def eval_vehicle_veri(model_path, veri_root, max_queries=None, batch=32,
                      gallery_stride=5, cache_dir=None, imagenet_norm=True):
    """Rank-1 for vehicle re-ID on VeRi-776 (image_query vs image_test).

    Production preprocessing is resize + ImageNet mean/std (matches
    reid_service.py vehicle path); imagenet_norm=False is a diagnostic
    [0,1] variant only. Standard protocol: same-id+same-cam gallery images
    are junk. Gallery is strided (default every 5th) for CPU-feasible eval;
    embeddings are cached per model+stride+norm so A/B re-runs are cheap.
    """
    import cv2
    import hashlib
    import numpy as np
    from edge.model_runtime import create_session

    root = Path(veri_root)
    q_files = sorted((root / "image_query").glob("*.jpg"))
    g_files = sorted((root / "image_test").glob("*.jpg"))[::gallery_stride]
    if max_queries:
        q_files = q_files[:max_queries]
    session = create_session(model_path)
    in_name = session.get_inputs()[0].name
    shape = session.get_inputs()[0].shape
    th, tw = int(shape[2]), int(shape[3])

    cache_key = hashlib.sha1(
        f"{model_path}|{gallery_stride}|{len(q_files)}|{len(g_files)}|norm={imagenet_norm}".encode()
    ).hexdigest()[:12]
    cache_path = (Path(cache_dir) if cache_dir else Path("data/eval")) / \
        f"veri_embs_{cache_key}.npz"
    if cache_path.exists():
        print(f"  loading cached embeddings {cache_path.name}...")
        cached = np.load(cache_path)
        q_embs, g_embs = cached["q"], cached["g"]
    else:
        def embed_files(files, tag):
            embs = []
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
            for i in range(0, len(files), batch):
                chunk = []
                for f in files[i:i + batch]:
                    img = cv2.imread(str(f))
                    img = cv2.resize(img, (tw, th))
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                    arr = rgb.transpose(2, 0, 1)
                    if imagenet_norm:
                        arr = (arr - mean) / std
                    chunk.append(arr)
                out = session.run(None, {in_name: np.stack(chunk).astype(np.float32)})[0]
                n = np.linalg.norm(out, axis=1, keepdims=True)
                n[n == 0] = 1.0
                embs.append(out / n)
                print(f"  {tag} {min(i + batch, len(files))}/{len(files)}...",
                      flush=True)
            return np.concatenate(embs, axis=0)

        q_embs = embed_files(q_files, "query")
        g_embs = embed_files(g_files, "gallery")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_path, q=q_embs, g=g_embs)

    q_meta = [parse_veri_name(f.name) for f in q_files]
    g_meta = [parse_veri_name(f.name) for f in g_files]
    print(f"  scoring {len(q_files)} queries vs {len(g_files)} gallery...")
    sims = q_embs @ g_embs.T
    hits = 0
    for qi, (qid, qcam) in enumerate(q_meta):
        order = np.argsort(-sims[qi])
        for oi in order:
            gid, gcam = g_meta[oi]
            if gid == qid and gcam == qcam:
                continue  # junk
            if gid == qid:
                hits += 1
            break
    rank1 = hits / len(q_files)
    return {"rank1": rank1, "n_queries": len(q_files), "n_gallery": len(g_files)}


def detect_persons_yolo(model, frame):
    """Return list of [x1,y1,x2,y2] person boxes (pixels)."""
    res = model(frame, classes=[0], verbose=False)[0]
    boxes = []
    for b in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
        boxes.append([x1, y1, x2, y2])
    return boxes


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area if area > 0 else 0.0


def build_tracks(frames_boxes, iou_thresh=0.3):
    """Greedy IoU linking of per-frame box lists into tracks. Returns tracks:
    each a list of (frame_idx, box)."""
    tracks = []  # list of {"last": box, "items": [...]}
    for fi, boxes in enumerate(frames_boxes):
        used = set()
        for tr in tracks:
            best, best_j = -1, 0.0
            for bi, b in enumerate(boxes):
                if bi in used:
                    continue
                j = iou(tr["last"], b)
                if j > best_j:
                    best, best_j = bi, j
            if best >= 0 and best_j >= iou_thresh:
                tr["items"].append((fi, boxes[best]))
                tr["last"] = boxes[best]
                used.add(best)
        for bi, b in enumerate(boxes):
            if bi not in used:
                tracks.append({"last": b, "items": [(fi, b)]})
    return [t["items"] for t in tracks if len(t["items"]) >= 3]


def crop_and_preprocess(frame, box, size=(128, 256)):
    import cv2
    import numpy as np
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(max(0, v)) for v in (box[0], box[1], box[2], box[3]))
    x2, y2 = min(w, x2 + 1), min(h, y2 + 1)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    resized = cv2.resize(crop, size)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return rgb.transpose(2, 0, 1)


def eval_person_footage(model_path, videos, frames_per_video=25,
                        windows_per_video=3, window_seconds=4.0):
    """Run footage eval. Returns dict with temporal, cross, margin, counts.

    For each video, decode `windows_per_video` contiguous windows of
    `window_seconds` at full fps (IoU linking works frame-to-frame), then
    keep crops ~2s apart within each track.
    """
    import cv2
    import numpy as np
    from ultralytics import YOLO
    from edge.model_runtime import create_session

    yolo = YOLO(str(REPO_ROOT / "yolov8n.pt"))
    session = create_session(model_path)
    in_name = session.get_inputs()[0].name

    def embed(crops):
        batch = np.stack(crops, axis=0).astype(np.float32)
        out = session.run(None, {in_name: batch})[0]
        n = np.linalg.norm(out, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return out / n

    all_track_embs = []  # list of list-of-embeddings per track
    for video in videos:
        cap = cv2.VideoCapture(video)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        win_len = int(fps * window_seconds)
        starts = [int(total * (i + 1) / (windows_per_video + 1)) - win_len // 2
                  for i in range(windows_per_video)]
        gap = max(1, int(fps * 2.0))
        for start in starts:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(total - 1, start)))
            frames, boxes_list = [], []
            for _ in range(win_len):
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)
                boxes_list.append(detect_persons_yolo(yolo, frame))
            tracks = build_tracks(boxes_list)
            for items in tracks:
                kept = [items[0]]
                for it in items[1:]:
                    if it[0] - kept[-1][0] >= gap:
                        kept.append(it)
                if len(kept) < 2:
                    kept = items[:2] if len(items) >= 2 else items
                crops = []
                for pos, box in kept:
                    c = crop_and_preprocess(frames[pos], box)
                    if c is not None:
                        crops.append(c)
                if len(crops) >= 2:
                    all_track_embs.append(embed(crops))
        cap.release()
    if len(all_track_embs) < 1:
        return {"temporal": 0.0, "cross": 1.0, "margin": -1.0,
                "n_tracks": 0, "note": "no tracks with >=2 crops found"}

    temporal_pairs = []
    for embs in all_track_embs:
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                temporal_pairs.append(float(embs[i] @ embs[j]))
    cross_pairs = []
    for i in range(len(all_track_embs)):
        for j in range(i + 1, len(all_track_embs)):
            a = all_track_embs[i][0]
            b = all_track_embs[j][0]
            cross_pairs.append(float(a @ b))
    temporal = float(np.mean(temporal_pairs)) if temporal_pairs else 0.0
    cross = float(np.mean(cross_pairs)) if cross_pairs else 1.0
    return {"temporal": temporal, "cross": cross, "margin": temporal - cross,
            "n_tracks": len(all_track_embs),
            "n_temporal_pairs": len(temporal_pairs),
            "n_cross_pairs": len(cross_pairs)}


def main() -> int:
    parser = argparse.ArgumentParser(description="IBVAP accuracy evaluation")
    parser.add_argument("--person-footage", action="store_true")
    parser.add_argument("--vehicle-veri", action="store_true")
    parser.add_argument("--face-lfw", action="store_true")
    parser.add_argument("--model", default="models/osnet_ain_x1_0.onnx")
    parser.add_argument("--lfw-dir", default="data/eval/lfw_funneled")
    parser.add_argument("--max-identities", type=int, default=200)
    parser.add_argument("--frames", type=int, default=25)
    parser.add_argument("--videos", nargs="*", default=["footage/cam1.mp4",
                                                        "footage/cam2.mp4"])
    parser.add_argument("--veri-root", default="data/eval/veri-776/VeRi")
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--imagenet-norm", action="store_true", default=True)
    parser.add_argument("--no-imagenet-norm", dest="imagenet_norm", action="store_false")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()
    if args.vehicle_veri:
        print(f"Evaluating {args.model} on VeRi-776...")
        try:
            res = eval_vehicle_veri(str(REPO_ROOT / args.model),
                                    str(REPO_ROOT / args.veri_root),
                                    max_queries=args.max_queries,
                                    batch=args.batch,
                                    imagenet_norm=args.imagenet_norm)
        except Exception as e:
            print(f"  [ERROR] eval failed: {e}")
            return 1
        ok = res["rank1"] >= GATE_VEHICLE_RANK1
        print(f"  [Rank-1={res['rank1']:.3f} (gate>={GATE_VEHICLE_RANK1}, "
              f"queries={res['n_queries']}, gallery={res['n_gallery']}) "
              f"[{'PASS' if ok else 'FAIL'}]")
        return 0 if ok else 1
    if args.face_lfw:
        print(f"Evaluating {args.model} on LFW Rank-1...")
        try:
            lfw = ensure_lfw()
            res = eval_face_rank1(str(REPO_ROOT / args.model), lfw,
                                  max_identities=args.max_identities)
        except Exception as e:
            print(f"  [ERROR] eval failed: {e}")
            return 1
        ok = res["rank1"] >= GATE_FACE_RANK1
        print(f"  Rank-1={res['rank1']:.3f} (gate>={GATE_FACE_RANK1}, "
              f"hits={res['hits']}/{res['n_identities']}) "
              f"[{'PASS' if ok else 'FAIL'}]")
        return 0 if ok else 1
    if not args.person_footage:
        parser.print_help()
        return 1
    videos = [str(REPO_ROOT / v) for v in args.videos]
    print(f"Evaluating {args.model} on {len(videos)} videos...")
    try:
        res = eval_person_footage(str(REPO_ROOT / args.model), videos,
                                  frames_per_video=args.frames)
    except Exception as e:
        print(f"  [ERROR] eval failed: {e}")
        return 1
    t_ok = res["temporal"] >= GATE_TEMPORAL
    m_ok = res["margin"] >= GATE_MARGIN
    print(f"  tracks={res['n_tracks']} temporal={res['temporal']:.3f} "
          f"(gate>={GATE_TEMPORAL}) [{'PASS' if t_ok else 'FAIL'}]")
    print(f"  cross={res['cross']:.3f} margin={res['margin']:.3f} "
          f"(gate>={GATE_MARGIN}) [{'PASS' if m_ok else 'FAIL'}]")
    return 0 if (t_ok and m_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
