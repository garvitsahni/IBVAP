"""
Detect API — YOLO inference for browser webcam frames with low-light enhancement.
Accepts base64 JPEG, returns bounding boxes. No DB storage.
"""
import base64
import logging
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/detect", tags=["detect"])

_model = None
_model_lock = __import__("threading").Lock()

_ocr_reader = None
_ocr_lock = __import__("threading").Lock()

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
                from ultralytics import YOLO
                logger.info("Loading YOLOv8s for /detect endpoint...")
                _model = YOLO("yolov8s.pt")
                logger.info("YOLOv8s loaded")
    return _model


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        with _ocr_lock:
            if _ocr_reader is None:
                try:
                    import easyocr
                    _ocr_reader = easyocr.Reader(['en'], gpu=False)
                    logger.info("EasyOCR loaded for plate reading")
                except Exception as e:
                    logger.warning(f"EasyOCR not available: {e}")
                    _ocr_reader = False  # sentinel — don't retry
    return _ocr_reader if _ocr_reader is not False else None


def _get_brightness(frame) -> float:
    return float(frame.mean())


def _apply_gamma(frame, gamma: float):
    inv = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv * 255 for i in range(256)]).astype("uint8")
    return frame.__class__.__bases__[0].__mro__[0]  # placeholder, cv2 below
    # Actually just use cv2
    import cv2
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


def _run_yolo(frame, conf_threshold: float) -> List[DetectionResult]:
    model = _get_model()
    results = model(frame, classes=list(TARGET_CLASSES), verbose=False, imgsz=1280)
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
            if cls_id in VEHICLE_CLASSES:
                plate_text = _read_plate(frame, x1, y1, x2, y2)
            dets.append(DetectionResult(
                bbox=BBoxResponse(x1=x1, y1=y1, x2=x2, y2=y2),
                confidence=round(conf, 3),
                class_name=CLASS_NAMES.get(cls_id, "unknown"),
                class_id=cls_id,
                plate_text=plate_text,
            ))
    return dets


def _read_plate(frame, x1, y1, x2, y2) -> str | None:
    """Crop vehicle region and run OCR to read plate text."""
    import cv2
    ocr = _get_ocr()
    if ocr is None:
        return None
    try:
        h, w = frame.shape[:2]
        ix1, iy1 = max(0, int(x1)), max(0, int(y1))
        ix2, iy2 = min(w, int(x2)), min(h, int(y2))
        crop = frame[iy1:iy2, ix1:ix2]
        if crop.size == 0:
            return None
        # Enhance contrast for plate readability
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        results = ocr.readtext(enhanced)
        if not results:
            return None
        # Filter for plate-like text (2-12 chars, alphanumeric)
        import re
        candidates = []
        for _, text, conf in results:
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if 2 <= len(cleaned) <= 12 and conf > 0.3:
                candidates.append(cleaned)
        if candidates:
            return max(candidates, key=len)
    except Exception as e:
        logger.debug(f"Plate OCR failed: {e}")
    return None


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

    h, w = frame.shape[:2]
    brightness = _get_brightness(frame)
    dark = brightness < 80
    conf = req.conf_threshold

    try:
        all_dets: List[DetectionResult] = []
        passes = 0
        import cv2

        # Pass 1: Always run on CLAHE-enhanced frame (works well for both light and dark)
        enhanced = _clahe(frame, clip=3.0, grid=8)
        all_dets.extend(_run_yolo(enhanced, conf))
        passes += 1

        if dark:
            # Pass 2: CLAHE + denoise + gamma 2.0
            step2 = _denoise(_clahe(frame, clip=4.0, grid=8))
            step2 = cv2.LUT(step2, np.array([(i / 255.0) ** (1.0 / 2.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step2, conf))
            passes += 1

            # Pass 3: CLAHE + denoise + gamma 3.0
            step3 = _denoise(_clahe(frame, clip=5.0, grid=8))
            step3 = cv2.LUT(step3, np.array([(i / 255.0) ** (1.0 / 3.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step3, conf))
            passes += 1

            # Pass 4: CLAHE + denoise + gamma 4.0
            step4 = _denoise(_clahe(frame, clip=6.0, grid=8))
            step4 = cv2.LUT(step4, np.array([(i / 255.0) ** (1.0 / 4.0) * 255 for i in range(256)]).astype("uint8"))
            all_dets.extend(_run_yolo(step4, conf))
            passes += 1

        dets = _dedup(all_dets)

    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")

    return DetectResponse(
        camera_id=req.camera_id,
        detections=dets,
        width=w,
        height=h,
        is_dark=dark,
        brightness=brightness,
        passes=passes,
    )
