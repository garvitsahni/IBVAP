"""
Plate OCR Service — reads text from license plate crops.
Runs as a separate process, receives plate crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PlateOCRService:
    """
    Plate text recognition service using EasyOCR or PaddleOCR.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = PlateOCRService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        ocr_engine: str = "easyocr",
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.ocr_type = ocr_engine
        self._engine = None

    def _load_engine(self):
        try:
            if self.ocr_type == "easyocr":
                import easyocr
                self._engine = easyocr.Reader(['en'], gpu=False)
                logger.info("EasyOCR engine loaded for plate OCR")
            elif self.ocr_type == "paddleocr":
                from paddleocr import PaddleOCR
                self._engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR engine loaded for plate OCR")
        except ImportError:
            logger.warning(f"{self.ocr_type} not installed — plate OCR will return None")
            self._engine = None

    def read_plate(self, plate_crop: np.ndarray) -> Optional[str]:
        if self._engine is None:
            return None

        try:
            if self.ocr_type == "easyocr":
                results = self._engine.readtext(plate_crop)
                if results:
                    text = " ".join([r[1] for r in results])
                    return text.upper().strip()
            elif self.ocr_type == "paddleocr":
                results = self._engine.ocr(plate_crop, cls=True)
                if results and results[0]:
                    text = " ".join([line[1][0] for line in results[0]])
                    return text.upper().strip()
        except Exception as e:
            logger.warning(f"Plate OCR failed: {e}")

        return None

    def run(self):
        self._load_engine()
        logger.info("Plate OCR service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Plate OCR received shutdown signal")
                break

            frame_id, camera_id, track_id, plate_crop = item
            try:
                plate_text = self.read_plate(plate_crop)
                self.res_queue.put((frame_id, camera_id, track_id, plate_text))
            except Exception as e:
                logger.error(f"Plate OCR failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, track_id, None))

        logger.info("Plate OCR service stopped")
