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
        nms_iou_threshold: float = 0.5,
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.nms_iou_threshold = nms_iou_threshold
        self._session = None
        self._input_name = None

    def _load_model(self):
        try:
            from edge.model_runtime import create_session
            self._session = create_session(self.model_path)
            self._input_name = self._session.get_inputs()[0].name
        except RuntimeError as e:
            logger.warning(f"{e}")
            logger.warning("Plate detector will return empty results (graceful fallback)")
            self._session = None
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

    def _parse_and_postprocess(
        self, output: np.ndarray, w_orig: int, h_orig: int
    ) -> List[dict]:
        """Parse YOLO raw output (1, 5, N) -> per-original-crop bbox dicts.

        Rows are [cx, cy, w, h, class_score] in input-pixel units (320x320).
        Applies score threshold + greedy NMS, then maps to original crop
        dimensions (matches detect_plates' production contract).
        """
        import cv2
        if output.ndim == 3:
            output = output[0]
        preds = output.T  # (N, 5): cx, cy, w, h, score
        scores = preds[:, 4]
        mask = scores >= self.conf_threshold
        sel = preds[mask]
        if sel.shape[0] == 0:
            return []
        boxes_xywh = np.stack(
            [sel[:, 0] - sel[:, 2] / 2, sel[:, 1] - sel[:, 3] / 2,
             sel[:, 2], sel[:, 3]], axis=1)
        keep = cv2.dnn.NMSBoxes(
            boxes_xywh.tolist(), scores[mask].astype(float).tolist(),
            float(self.conf_threshold), float(self.nms_iou_threshold))
        plates = []
        sx, sy = w_orig / PLATE_INPUT_WIDTH, h_orig / PLATE_INPUT_HEIGHT
        for i in (np.array(keep).flatten() if len(keep) else []):
            x1 = max(0.0, boxes_xywh[i, 0] * sx)
            y1 = max(0.0, boxes_xywh[i, 1] * sy)
            x2 = min(float(w_orig), (boxes_xywh[i, 0] + boxes_xywh[i, 2]) * sx)
            y2 = min(float(h_orig), (boxes_xywh[i, 1] + boxes_xywh[i, 3]) * sy)
            plates.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": float(scores[mask][i]),
            })
        return plates

    def detect_plates(self, vehicle_crop: np.ndarray) -> List[dict]:
        if self._session is None:
            return []

        try:
            blob = self._preprocess(vehicle_crop)
            outputs = self._session.run(None, {self._input_name: blob})
            h_orig, w_orig = vehicle_crop.shape[:2]
            return self._parse_and_postprocess(outputs[0], w_orig, h_orig)
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
