"""
Shared detection service — loads YOLOv8n once, serves batched inference
to camera workers via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

TARGET_CLASSES = {0, 2, 3, 5, 7}
CLASS_NAMES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


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

            frame_id, camera_id, frame = item
            try:
                detections = self._run_inference(frame)
                self.res_queue.put((frame_id, camera_id, detections))
            except Exception as e:
                logger.error(f"Detection failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, []))

        logger.info("Detection service stopped")
