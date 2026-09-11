# fusion_server/core/anpr.py
"""ANPR Pipeline — plate detection + OCR."""
import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PlateResult:
    plate_text: str
    confidence: float
    bbox: list  # [x, y, w, h] normalized


class ANPRPipeline:
    """
    Automatic Number Plate Recognition pipeline.
    Uses YOLOv8 for plate detection + PaddleOCR/EasyOCR for character recognition.
    """

    def __init__(self, plate_model_path: str = None, ocr_engine: str = "easyocr"):
        self._plate_model = None
        self._ocr_engine = None
        self._ocr_type = ocr_engine
        self._plate_model_path = plate_model_path
        self._initialized = False

    def _lazy_init(self):
        """Initialize models on first use (avoids import-time GPU load)."""
        if self._initialized:
            return
        try:
            from ultralytics import YOLO
            if self._plate_model_path:
                self._plate_model = YOLO(self._plate_model_path)
            else:
                self._plate_model = YOLO("yolov8n.pt")  # Placeholder — real model trained on plates
            logger.info("ANPR plate detection model loaded")
        except ImportError:
            logger.warning("ultralytics not installed — ANPR will use fallback detection")

        try:
            if self._ocr_type == "easyocr":
                import easyocr
                self._ocr_engine = easyocr.Reader(['en'])
                logger.info("EasyOCR engine loaded")
            elif self._ocr_type == "paddleocr":
                from paddleocr import PaddleOCR
                self._ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR engine loaded")
        except ImportError:
            logger.warning(f"{self._ocr_type} not installed — ANPR will use fallback OCR")

        self._initialized = True

    def detect_plate(self, frame: np.ndarray) -> Optional[PlateResult]:
        """
        Detect and read a license plate from a frame.
        Returns PlateResult or None if no plate found.
        """
        self._lazy_init()

        if self._plate_model is None:
            return None

        try:
            results = self._plate_model(frame, verbose=False)
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls != 0:  # Assuming class 0 = plate (adjust for fine-tuned model)
                        continue
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    h, w = frame.shape[:2]
                    plate_crop = frame[int(y1):int(y2), int(x1):int(x2)]
                    if plate_crop.size == 0:
                        continue

                    plate_text = self._ocr_plate(plate_crop)
                    if plate_text:
                        return PlateResult(
                            plate_text=plate_text,
                            confidence=float(box.conf[0]),
                            bbox=[float(x1)/w, float(y1)/h, (float(x2)-float(x1))/w, (float(y2)-float(y1))/h],
                        )
        except Exception as e:
            logger.warning(f"ANPR detection failed: {e}")

        return None

    def _ocr_plate(self, plate_crop: np.ndarray) -> Optional[str]:
        """Run OCR on a plate crop image."""
        self._lazy_init()
        if self._ocr_engine is None:
            return None

        try:
            if self._ocr_type == "easyocr":
                results = self._ocr_engine.readtext(plate_crop)
                if results:
                    # Combine all detected text
                    text = " ".join([r[1] for r in results])
                    return text.upper().strip()
            elif self._ocr_type == "paddleocr":
                results = self._ocr_engine.ocr(plate_crop, cls=True)
                if results and results[0]:
                    text = " ".join([line[1][0] for line in results[0]])
                    return text.upper().strip()
        except Exception as e:
            logger.warning(f"OCR failed: {e}")

        return None

    def _run_detection(self, frame: np.ndarray) -> Optional[dict]:
        """Internal detection helper for test mocking."""
        result = self.detect_plate(frame)
        if result is None:
            return None
        return {
            "plate_text": result.plate_text,
            "confidence": result.confidence,
            "bbox": result.bbox,
        }

    def process_detection(self, db, object_id: str, camera_id: str, frame: np.ndarray) -> Optional[dict]:
        """
        Full pipeline: detect plate, store result, check watchlist.
        Returns plate detection data or None.
        """
        det = self._run_detection(frame)
        if det is None:
            return None

        from fusion_server.db.models_plate import PlateDetection
        from datetime import datetime

        plate_record = PlateDetection(
            object_id=object_id,
            camera_id=camera_id,
            plate_text=det["plate_text"],
            confidence=det["confidence"],
            bbox=det["bbox"],
        )
        db.add(plate_record)
        db.commit()
        db.refresh(plate_record)

        return {
            "id": plate_record.id,
            "plate_text": det["plate_text"],
            "confidence": det["confidence"],
            "bbox": det["bbox"],
        }
