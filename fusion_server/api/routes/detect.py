"""
Detect API — YOLO inference for browser webcam frames with low-light enhancement.
Accepts base64 JPEG, returns bounding boxes. No DB storage.

IMPORTANT: all synchronous heavy work (decode helpers, YOLO, OCR) runs in the
threadpool via run_in_threadpool — NEVER directly on the asyncio event loop.
Blocking the loop stalls every other request (edge event publishes, SSE, stats).
"""
import asyncio
import base64
import logging
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/detect", tags=["detect"])

_model = None
_model_lock = __import__("threading").Lock()

_ocr_reader = None
_ocr_lock = __import__("threading").Lock()

# Single-flight guard: only one YOLO+OCR run at a time so concurrent frames
# can't pile up threads and starve the shared threadpool.
_detect_sem = __import__("threading").Semaphore(1)

VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck
TARGET_CLASSES = {0, 2, 3, 5, 7}
CLASS_NAMES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class DetectRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded JPEG image")
    camera_id: str = Field(default="browser-webcam")
    conf_threshold: float = Field(default=0.10, ge=0.0, le=1.0)


class BBoxResponse(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionResult(BaseModel):
    bbox: BBoxResponse
    confidence: float
    class_name: str
    class_id: int
    plate_text: str | None = None


class DetectResponse(BaseModel):
    camera_id: str
    detections: List[DetectionResult]
    width: int
    height: int
    is_dark: bool
    brightness: float
    passes: int


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import os
                from ultralytics import YOLO
                # YOLO_MODEL picks the detector (see docs/yolo_benchmark.md).
                # Measured: v8m GPU 29.3 FPS (real-time), v8m CPU 2.4 FPS —
                # so GPU tier defaults to v8m, CPU tier to v8n.
                weights = os.environ.get("YOLO_MODEL")
                if weights and not os.path.exists(weights):
                    # Fine-tuned weights pinned but file absent (fresh clone?) —
                    # fall back to stock tier default instead of 500ing.
                    logger.warning(f"YOLO_MODEL={weights} not found — falling back to stock weights")
                    weights = None
                if not weights:
                    try:
                        import torch
                        weights = "yolov8m.pt" if torch.cuda.is_available() else "yolov8n.pt"
                    except Exception:
                        weights = "yolov8n.pt"
                logger.info(f"Loading {weights} for /detect endpoint...")
                _model = YOLO(weights)
                logger.info(f"{weights} loaded")
    return _model


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        with _ocr_lock:
            if _ocr_reader is None:
                try:
                    import easyocr
                    _ocr_reader = easyocr.Reader(['en'], gpu=False)
                    logger.info("[PLATE OCR] EasyOCR engine loaded and ready")
                except Exception as e:
                    logger.warning(f"EasyOCR not available: {e}")
                    _ocr_reader = False  # sentinel — don't retry
    return _ocr_reader if _ocr_reader is not False else None


_plate_detector = None
_plate_detector_lock = __import__("threading").Lock()


def _get_plate_detector():
    global _plate_detector
    if _plate_detector is None:
        with _plate_detector_lock:
            if _plate_detector is None:
                try:
                    import os
                    if os.path.exists("models/plate_detector.onnx"):
                        import multiprocessing
                        from edge.plate_detector import PlateDetectorService
                        q = multiprocessing.Queue()
                        svc = PlateDetectorService(q, q, model_path="models/plate_detector.onnx")
                        svc._load_model()
                        if svc._session is not None:
                            _plate_detector = svc
                            logger.info("[PLATE DET] Loaded models/plate_detector.onnx for /detect")
                        else:
                            _plate_detector = False
                    else:
                        _plate_detector = False
                except Exception as e:
                    logger.warning(f"Plate detector model not available: {e}")
                    _plate_detector = False
    return _plate_detector if _plate_detector is not False else None


def _get_brightness(frame) -> float:
    return float(frame.mean())


def _apply_gamma(frame, gamma: float):
    import cv2
    inv = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(frame, table)


def _clahe(frame, clip=3.0, grid=8):
    import cv2
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _denoise(frame):
    import cv2
    return cv2.bilateralFilter(frame, 9, 75, 75)


def _run_yolo(
    frame,
    conf_threshold: float,
    camera_id: str = "browser-webcam",
    plate_reads: list | None = None,
) -> List[DetectionResult]:
    model = _get_model()
    # 640 matches the webcam upload width — 1280 upscaled x2 for no extra
    # detail while quadrupling CPU time (measured 0.77s -> ~0.2s/pass).
    results = model(frame, classes=list(TARGET_CLASSES), verbose=False, imgsz=640)
    dets = []
    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in TARGET_CLASSES:
                continue
            conf = float(box.conf[0])
            if conf < conf_threshold:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            plate_text = None
            # OCR only when the caller wants plate results collected; multi-pass
            # dark frames pass plate_reads=None and OCR runs once after dedup.
            if plate_reads is not None and cls_id in VEHICLE_CLASSES:
                plate_text = _read_plate(frame, x1, y1, x2, y2)
                if plate_text:
                    logger.info(f"[PLATE READ] {CLASS_NAMES.get(cls_id)} -> '{plate_text}'")
                    if plate_reads is not None:
                        # Collected here; SSE broadcast happens on the event loop
                        plate_reads.append({
                            "camera_id": camera_id,
                            "plate_text": plate_text,
                            "class_name": CLASS_NAMES.get(cls_id),
                            "confidence": round(conf, 3),
                        })
            dets.append(DetectionResult(
                bbox=BBoxResponse(x1=x1, y1=y1, x2=x2, y2=y2),
                confidence=round(conf, 3),
                class_name=CLASS_NAMES.get(cls_id, "unknown"),
                class_id=cls_id,
                plate_text=plate_text,
            ))
    return dets


def _read_plate(frame, x1, y1, x2, y2) -> str | None:
    """Crop vehicle region, detect plate (or focus on lower-center), upscale, OCR.

    Strategies run in order:
    0. Exact plate detection via trained PlateDetectorService on vehicle crop
    1. Lower-center strip (where plates typically are)
    2. Bumper area
    3. Full vehicle crop (fallback)
    The FIRST candidate with >=4 plate-like chars wins.
    """
    import cv2
    ocr = _get_ocr()
    if ocr is None:
        return None
    try:
        h, w = frame.shape[:2]
        ix1, iy1 = max(0, int(x1)), max(0, int(y1))
        ix2, iy2 = min(w, int(x2)), min(h, int(y2))
        vw = ix2 - ix1
        vh = iy2 - iy1
        if vw < 20 or vh < 20:
            return None

        vehicle_crop = frame[iy1:iy2, ix1:ix2]

        # --- Strategy 0: Exact plate detection via trained plate detector ---
        detector = _get_plate_detector()
        if detector is not None and vehicle_crop.size > 0:
            try:
                plates = detector.detect_plates(vehicle_crop)
                if plates:
                    best_plate = max(plates, key=lambda p: (p["bbox"][2] - p["bbox"][0]) * (p["bbox"][3] - p["bbox"][1]))
                    px1, py1, px2, py2 = best_plate["bbox"]
                    p_crop = vehicle_crop[py1:py2, px1:px2]
                    if p_crop.size > 0:
                        candidates = _ocr_region(p_crop)
                        if candidates:
                            best = max(candidates, key=len)
                            if len(best) >= 4:
                                return best
            except Exception as e:
                logger.debug(f"Detector-assisted plate crop failed: {e}")

        # --- Strategy 1: Focus on lower-center strip (where plates are) ---
        plate_y1 = iy1 + int(vh * 0.55)
        plate_y2 = iy2
        plate_x1 = ix1 + int(vw * 0.05)
        plate_x2 = ix2 - int(vw * 0.05)
        plate_crop = frame[plate_y1:plate_y2, plate_x1:plate_x2]

        # --- Strategy 2: Bottom quarter (very tight on bumper area) ---
        bump_y1 = iy1 + int(vh * 0.7)
        bump_y2 = iy2
        bump_crop = frame[bump_y1:bump_y2, ix1:ix2]

        # --- Strategy 3: Full vehicle crop (fallback) ---
        full_crop = vehicle_crop

        fallback = None
        for crop in (plate_crop, bump_crop, full_crop):
            if crop is None or crop.size == 0:
                continue
            candidates = _ocr_region(crop)
            if not candidates:
                continue
            best = max(candidates, key=len)
            if len(best) >= 6:
                return best
            if fallback is None:
                fallback = best
        return fallback
    except Exception as e:
        logger.debug(f"Plate OCR failed: {e}")
    return None


def _parse_ocr_results(results) -> list:
    """Filter EasyOCR output down to plate-like candidates (existing rules)."""
    import re
    candidates = []
    if not results:
        return candidates
    # Combine all detections in reading order (left-to-right, top-to-bottom)
    sorted_results = sorted(results, key=lambda r: (r[0][0][1], r[0][0][0]))
    combined = "".join([re.sub(r'[^A-Z0-9]', '', r[1].upper()) for r in sorted_results])
    if 4 <= len(combined) <= 16:
        candidates.append(combined)
    # Also check individual detections for short but valid plate fragments
    for _, text, conf in results:
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        if 4 <= len(cleaned) <= 12 and conf > 0.1:
            candidates.append(cleaned)
    return candidates


def _ocr_region(crop_img) -> list:
    """OCR a cropped region with capped upscale. Returns plate-like strings.

    Budget: at most 2 readtext calls per region (enhanced pass, then Otsu
    only if the first found nothing >=6 chars); readtext is restricted to the
    plate allowlist. Width capped at ~1000px — 4x-upscaling full vehicle
    crops produced 2700px images that took ~9s each to OCR.
    """
    import cv2
    ocr = _get_ocr()
    if ocr is None:
        return []

    ch, cw = crop_img.shape[:2]
    if ch < 10 or cw < 30:
        return []

    # Upscale enough for OCR but never beyond ~1000px wide
    scale = 4 if cw * 4 <= 1000 else max(2, 1000 // cw)
    upscaled = cv2.resize(crop_img, (cw * scale, ch * scale), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    allow = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    try:
        candidates = _parse_ocr_results(ocr.readtext(enhanced, allowlist=allow))
        if any(len(c) >= 6 for c in candidates):
            return candidates
        _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        candidates.extend(_parse_ocr_results(ocr.readtext(otsu, allowlist=allow)))
    except Exception as e:
        logger.debug(f"OCR pass failed: {e}")
    return candidates


# Debug capture for car-miss diagnosis (Phase 1 of car+plate plan).
# IBVAP_DEBUG_DETECT=1 dumps raw frames + raw predictions + final dets to
# IBVAP_DEBUG_DIR (default debug/car-miss). Capped per process; never raises.
_debug_dump_count = 0


def _maybe_debug_dump(frame, raw_dets, final_dets, meta) -> None:
    """Best-effort debug dump. Reads env itself so tests can toggle it."""
    import cv2
    import json
    import os
    import time
    global _debug_dump_count
    try:
        if os.environ.get("IBVAP_DEBUG_DETECT") != "1":
            return
        max_frames = int(os.environ.get("IBVAP_DEBUG_MAX_FRAMES", "300"))
        if _debug_dump_count >= max_frames:
            if _debug_dump_count == max_frames:
                logger.warning(f"[DEBUG_DETECT] cap reached ({max_frames} frames) — stopping dumps")
                _debug_dump_count += 1
            return
        outdir = os.environ.get("IBVAP_DEBUG_DIR", "debug/car-miss")
        os.makedirs(outdir, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        stem = f"frame_{ts}_{_debug_dump_count:04d}"
        cv2.imwrite(os.path.join(outdir, stem + ".jpg"), frame)
        with open(os.path.join(outdir, stem + ".json"), "w") as f:
            json.dump({
                "meta": meta,
                "raw_predictions": [
                    {"class_id": d.class_id, "class_name": d.class_name,
                     "confidence": d.confidence,
                     "bbox": [d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2]}
                    for d in sorted(raw_dets, key=lambda d: d.confidence, reverse=True)[:50]
                ],
                "final_detections": [
                    {"class_id": d.class_id, "class_name": d.class_name,
                     "confidence": d.confidence,
                     "bbox": [d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2],
                     "plate_text": d.plate_text}
                    for d in final_dets
                ],
            }, f)
        _debug_dump_count += 1
    except Exception as e:
        logger.debug(f"[DEBUG_DETECT] dump failed (non-fatal): {e}")


def _dedup(dets: List[DetectionResult], iou_thresh=0.4) -> List[DetectionResult]:
    if not dets:
        return dets
    dets.sort(key=lambda d: d.confidence, reverse=True)
    keep = []
    for d in dets:
        is_dup = False
        for k in keep:
            if d.class_id != k.class_id:
                continue
            ix1 = max(d.bbox.x1, k.bbox.x1)
            iy1 = max(d.bbox.y1, k.bbox.y1)
            ix2 = min(d.bbox.x2, k.bbox.x2)
            iy2 = min(d.bbox.y2, k.bbox.y2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_d = (d.bbox.x2 - d.bbox.x1) * (d.bbox.y2 - d.bbox.y1)
            area_k = (k.bbox.x2 - k.bbox.x1) * (k.bbox.y2 - k.bbox.y1)
            union = area_d + area_k - inter
            if union > 0 and inter / union > iou_thresh:
                is_dup = True
                break
        if not is_dup:
            keep.append(d)
    return keep


def _read_plates_for_dets(enhanced, dets: List[DetectionResult], camera_id: str) -> dict:
    """Plate OCR for already-deduped dets on the enhanced frame.

    SYNC/blocking (EasyOCR on CPU costs seconds) — call from a worker thread
    (via _process_frame run_plates=True) or from _plate_ocr_job, never on the
    event loop. Returns {"detections": dets (mutated + maybe appended),
    "plate_reads": [...]}. Never raises.
    """
    plate_reads: list = []
    try:
        # Plate OCR: once per unique vehicle, on the CLAHE-enhanced frame.
        for det in dets:
            if det.class_id not in VEHICLE_CLASSES:
                continue
            text = _read_plate(enhanced, det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2)
            if text:
                det.plate_text = text
                plate_reads.append({
                    "camera_id": camera_id,
                    "plate_text": text,
                    "class_name": det.class_name,
                    "confidence": det.confidence,
                })

        # Standalone / held plate detection: if no vehicle has a plate (e.g. user showing
        # a license plate, phone screen, or card directly to the webcam), run the plate
        # detector on the enhanced frame.
        if not any(d.plate_text for d in dets):
            detector = _get_plate_detector()
            if detector is not None:
                try:
                    frame_plates = detector.detect_plates(enhanced)
                    for fp in frame_plates:
                        fx1, fy1, fx2, fy2 = fp["bbox"]
                        p_crop = enhanced[fy1:fy2, fx1:fx2]
                        if p_crop.size > 0:
                            candidates = _ocr_region(p_crop)
                            if candidates:
                                text = max(candidates, key=len)
                                if len(text) >= 4:
                                    attached = False
                                    for d in dets:
                                        if not (fx2 < d.bbox.x1 or fx1 > d.bbox.x2 or fy2 < d.bbox.y1 or fy1 > d.bbox.y2):
                                            d.plate_text = text
                                            attached = True
                                            break
                                    if not attached:
                                        dets.append(DetectionResult(
                                            bbox=BBoxResponse(x1=float(fx1), y1=float(fy1), x2=float(fx2), y2=float(fy2)),
                                            confidence=round(float(fp["confidence"]), 3),
                                            class_name="plate",
                                            class_id=2,
                                            plate_text=text,
                                        ))
                                    plate_reads.append({
                                        "camera_id": camera_id,
                                        "plate_text": text,
                                        "class_name": "plate",
                                        "confidence": round(float(fp["confidence"]), 3),
                                    })
                                    break
                except Exception as e:
                    logger.debug(f"Frame-level plate detection failed: {e}")
    except Exception as e:
        logger.debug(f"Plate OCR block failed (non-fatal): {e}")
    return {"detections": dets, "plate_reads": plate_reads}


# Only one background plate-OCR job at a time — OCR on CPU is slow and frames
# arrive at 2Hz; without the guard jobs pile up unboundedly.
_ocr_busy = __import__("threading").Event()

# Per-camera OCR cooldown (seconds): a held-up car would otherwise retrigger
# a multi-second CPU-pegging OCR job on nearly every frame. Plates barely
# change frame-to-frame, so one attempt per camera per cooldown is plenty —
# toasts still arrive, the box stays responsive.
OCR_COOLDOWN_S = 10.0
_ocr_last_run: dict = {}


async def _plate_ocr_job(frame, dets: List[DetectionResult], camera_id: str) -> None:
    """Background plate OCR for dets already returned to the client.

    Boxes render instantly from the HTTP response; plate texts arrive seconds
    later via plate_read SSE (Rule 4: enrichment never blocks delivery).
    Best-effort: skips when a previous job is still running, never raises.
    """
    if _ocr_busy.is_set():
        return
    import time as _time3
    now = _time3.monotonic()
    last = _ocr_last_run.get(camera_id, 0.0)
    if now - last < OCR_COOLDOWN_S:
        return
    _ocr_last_run[camera_id] = now
    _ocr_busy.set()
    try:
        # Top-2 vehicles only — bounds worst-case CPU time per job.
        vehicles = sorted(
            (d for d in dets if d.class_id in VEHICLE_CLASSES),
            key=lambda d: d.confidence, reverse=True,
        )[:2]
        if not vehicles:
            return
        enhanced = await run_in_threadpool(_clahe, frame)
        from fusion_server.services.broadcaster import get_broadcaster
        for det in vehicles:
            try:
                text = await run_in_threadpool(
                    _read_plate, enhanced,
                    det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2)
            except Exception as e:
                logger.debug(f"Background plate read failed (non-fatal): {e}")
                continue
            if text:
                try:
                    await get_broadcaster().broadcast_plate_read({
                        "camera_id": camera_id,
                        "plate_text": text,
                        "class_name": det.class_name,
                        "confidence": det.confidence,
                    })
                except Exception:
                    pass  # Never fail on broadcast
    finally:
        _ocr_busy.clear()


def _process_frame(frame, conf: float, camera_id: str, run_plates: bool = True) -> dict:
    """
    Multi-pass low-light YOLO detection (+ plate OCR unless run_plates=False).
    SYNC — must only ever run inside run_in_threadpool, never on the event loop.

    run_plates=False gives the fast path: YOLO boxes only, no OCR. Plate work
    (EasyOCR on CPU costs seconds per vehicle — responses arrived past the
    overlay's 3s stale filter, so car boxes NEVER rendered) runs in
    _plate_ocr_job as a background task and reports via plate_read SSE.
    """
    import cv2

    h, w = frame.shape[:2]
    brightness = _get_brightness(frame)
    dark = brightness < 80

    all_dets: List[DetectionResult] = []
    plate_reads: list = []
    passes = 0

    try:
        # All YOLO passes are DETECTION-ONLY (plate_reads=None); plate OCR runs
        # once after dedup below. Previously every dark pass re-ran full plate
        # OCR per vehicle (4 passes x ~12 readtext calls => ~15min requests).
        # Pass 1: Always run on CLAHE-enhanced frame (works well for both light and dark)
        enhanced = _clahe(frame, clip=3.0, grid=8)
        all_dets.extend(_run_yolo(enhanced, conf, camera_id=camera_id, plate_reads=None))
        passes += 1

        if dark:
            # Pass 2: CLAHE + denoise + gamma 2.0
            step2 = _denoise(_clahe(frame, clip=4.0, grid=8))
            step2 = cv2.LUT(step2, np.array([(i / 255.0) ** (1.0 / 2.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step2, conf, camera_id=camera_id, plate_reads=None))
            passes += 1

            # Pass 3: CLAHE + denoise + gamma 3.0
            step3 = _denoise(_clahe(frame, clip=5.0, grid=8))
            step3 = cv2.LUT(step3, np.array([(i / 255.0) ** (1.0 / 3.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step3, conf, camera_id=camera_id, plate_reads=None))
            passes += 1

            # Pass 4: CLAHE + denoise + gamma 4.0
            step4 = _denoise(_clahe(frame, clip=6.0, grid=8))
            step4 = cv2.LUT(step4, np.array([(i / 255.0) ** (1.0 / 4.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step4, conf, camera_id=camera_id, plate_reads=None))
            passes += 1

        dets = _dedup(all_dets)

        # Plate OCR (slow on CPU) — synchronous only when the caller asked for
        # it (offline scripts/tests). The live endpoint passes run_plates=False
        # and gets plates via _plate_ocr_job + SSE instead (see below).
        if run_plates:
            plates_result = _read_plates_for_dets(enhanced, dets, camera_id)
            dets = plates_result["detections"]
            plate_reads = plates_result["plate_reads"]

        # Debug capture for car-miss diagnosis: raw probe at conf 0.01 on the
        # same enhanced frame, plus final post-dedup dets. Flag-gated, capped,
        # never raises (see _maybe_debug_dump). Detection-only (plate_reads=None).
        try:
            import os
            if os.environ.get("IBVAP_DEBUG_DETECT") == "1":
                raw_probe = _run_yolo(enhanced, 0.01, camera_id=camera_id, plate_reads=None)
                _maybe_debug_dump(frame, raw_probe, dets, {
                    "width": w, "height": h, "brightness": brightness,
                    "is_dark": dark, "passes": passes,
                })
        except Exception as e:
            logger.debug(f"[DEBUG_DETECT] probe failed (non-fatal): {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")

    return {
        "detections": dets,
        "width": w,
        "height": h,
        "is_dark": dark,
        "brightness": brightness,
        "passes": passes,
        "plate_reads": plate_reads,
    }


@router.post("", response_model=DetectResponse)
async def detect_objects(req: DetectRequest):
    """Run YOLO detection with multi-pass low-light enhancement."""
    try:
        img_bytes = base64.b64decode(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    try:
        import cv2
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image decode error: {e}")

    # Single-flight: reject instead of queueing unbounded YOLO work
    if not _detect_sem.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Detection busy — retry next frame")
    try:
        # Fast path: YOLO boxes only (no OCR) so the response beats the
        # overlay's 3s stale filter. Plates follow via _plate_ocr_job + SSE.
        result = await run_in_threadpool(_process_frame, frame, req.conf_threshold, req.camera_id, False)
    finally:
        _detect_sem.release()

    # Background plate OCR on the event loop (never from a worker thread, and
    # never blocking the response above). Skips itself when busy.
    try:
        asyncio.ensure_future(_plate_ocr_job(frame, result["detections"], req.camera_id))
    except Exception:
        pass  # Never block detection on scheduling failure

    return DetectResponse(
        camera_id=req.camera_id,
        detections=result["detections"],
        width=result["width"],
        height=result["height"],
        is_dark=result["is_dark"],
        brightness=result["brightness"],
        passes=result["passes"],
    )
