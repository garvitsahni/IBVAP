"""
Shared detection service — loads YOLOv8n once, serves batched inference
to camera workers via multiprocessing.Queue.

Supports SWITCH_MODEL protocol for night mode weight switching.
"""
import numpy as np
import multiprocessing
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

TARGET_CLASSES = {0, 2, 3, 5, 7}
CLASS_NAMES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Sentinel value for model switching — sent through req_queue
SWITCH_MODEL = "SWITCH_MODEL"


def motion_detection(frame: np.ndarray, prev_frame: np.ndarray, min_area: int = 500) -> List[Dict]:
    """Frame-difference motion detection fallback."""
    import cv2
    if prev_frame is None:
        return []
    gray1 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        confidence = min(area / 10000.0, 1.0)
        detections.append({
            "bbox": [float(x), float(y), float(x + w), float(y + h)],
            "confidence": confidence,
            "class_id": 0,
            "class_name": "person",
        })
    return detections


class DetectionService:
    """
    Runs YOLOv8n inference. Designed to run as a separate process.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = DetectionService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.35,
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._model = None

    def _load_model(self):
        from ultralytics import YOLO
        logger.info(f"Loading YOLOv8n from {self.model_path}...")
        self._model = YOLO(self.model_path)
        logger.info("YOLOv8n loaded successfully")

    def _run_inference(self, frame: np.ndarray) -> List[Dict]:
        if self._model is None:
            self._load_model()

        results = self._model(frame, classes=list(TARGET_CLASSES), verbose=False)

        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in TARGET_CLASSES:
                    continue
                conf = float(box.conf[0])
                if conf < self.conf_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls_id,
                    "class_name": CLASS_NAMES.get(cls_id, "unknown"),
                })

        return detections

    def run(self):
        self._load_model()
        logger.info("Detection service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Detection service received shutdown signal")
                break

            # Handle SWITCH_MODEL command: ("SWITCH_MODEL", model_path)
            if isinstance(item, tuple) and len(item) == 2 and item[0] == SWITCH_MODEL:
                new_path = item[1]
                try:
                    self.set_model(new_path)
                    logger.info(f"Detection model switched to {new_path}")
                except Exception as e:
                    logger.error(f"Failed to switch model to {new_path}: {e}")
                continue

            frame_id, camera_id, frame = item
            try:
                detections = self._run_inference(frame)
                self.res_queue.put((frame_id, camera_id, detections))
            except Exception as e:
                logger.error(f"Detection failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, []))

        logger.info("Detection service stopped")

    def set_model(self, path: str):
        """Switch to a different model weights file."""
        from ultralytics import YOLO
        logger.info(f"Switching detection model to {path}")
        self.model_path = path
        self._model = YOLO(path)
