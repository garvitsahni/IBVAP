"""
Plate Detector Service — detects license plate regions in vehicle crops.
Runs as a separate process, receives vehicle crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

PLATE_INPUT_HEIGHT = 320
PLATE_INPUT_WIDTH = 320


class PlateDetectorService:
    """
    Plate detection service using ONNX model.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = PlateDetectorService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "models/plate_detector.onnx",
        conf_threshold: float = 0.5,
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._session = None
        self._input_name = None

    def _load_model(self):
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(self.model_path)
            self._input_name = self._session.get_inputs()[0].name
            logger.info(f"Plate detector model loaded from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load plate detector from {self.model_path}: {e}")
            logger.warning("Plate detector will return empty results (graceful fallback)")
            self._session = None

    def _preprocess(self, vehicle_crop: np.ndarray) -> np.ndarray:
        import cv2
        resized = cv2.resize(vehicle_crop, (PLATE_INPUT_WIDTH, PLATE_INPUT_HEIGHT))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, 0)
        return blob

    def detect_plates(self, vehicle_crop: np.ndarray) -> List[dict]:
        if self._session is None:
            return []

        try:
            import cv2
            blob = self._preprocess(vehicle_crop)
            outputs = self._session.run(None, {self._input_name: blob})

            plates = []
            output = outputs[0]
            if output.ndim == 3:
                output = output[0]

            h_orig, w_orig = vehicle_crop.shape[:2]

            for detection in output:
                if len(detection) >= 6:
                    x1, y1, x2, y2 = detection[:4]
                    conf = float(detection[4])
                    if conf < self.conf_threshold:
                        continue

                    # Scale to original crop dimensions
                    x1_scaled = max(0, x1 / PLATE_INPUT_WIDTH * w_orig)
                    y1_scaled = max(0, y1 / PLATE_INPUT_HEIGHT * h_orig)
                    x2_scaled = min(w_orig, x2 / PLATE_INPUT_WIDTH * w_orig)
                    y2_scaled = min(h_orig, y2 / PLATE_INPUT_HEIGHT * h_orig)

                    plates.append({
                        "bbox": [int(x1_scaled), int(y1_scaled), int(x2_scaled), int(y2_scaled)],
                        "confidence": conf,
                    })

            return plates
        except Exception as e:
            logger.error(f"Plate detection failed: {e}")
            return []

    def run(self):
        self._load_model()
        logger.info("Plate detector service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Plate detector received shutdown signal")
                break

            frame_id, camera_id, track_id, vehicle_crop = item
            try:
                plates = self.detect_plates(vehicle_crop)
                self.res_queue.put((frame_id, camera_id, track_id, plates))
            except Exception as e:
                logger.error(f"Plate detection failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, track_id, []))

        logger.info("Plate detector service stopped")
