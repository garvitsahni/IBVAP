"""
Face Detection Service — detects faces in person crops using RetinaFace/SCRFD.
Runs as a separate process, receives person crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Standard face detection input size
FACE_INPUT_SIZE = 640


class FaceDetectorService:
    """
    Face detection service using InsightFace (RetinaFace/SCRFD).

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = FaceDetectorService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        det_size: int = 640,
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.det_size = det_size
        self._app = None

    def _load_model(self):
        """Load InsightFace face detection model."""
        try:
            from insightface.app import FaceAnalysis
            self._app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection"],
            )
            self._app.prepare(ctx_id=-1, det_size=(self.det_size, self.det_size))
            logger.info(f"Face detection model loaded (det_size={self.det_size})")
        except ImportError:
            logger.warning(
                "insightface not installed. Install with: pip install insightface>=0.7.3"
            )
            self._app = None
        except Exception as e:
            logger.warning(f"Failed to load face detection model: {e}")
            self._app = None

    def detect_faces(self, crop: np.ndarray) -> List[dict]:
        """
        Detect faces in a person crop.

        Args:
            crop: BGR numpy array (person crop from frame)

        Returns:
            List of dicts with keys: bbox, confidence, bbox_in_crop
            bbox is in crop-local coordinates [x1, y1, x2, y2]
        """
        if self._app is None:
            return []

        try:
            faces = self._app.get(crop)
            results = []
            for face in faces:
                bbox = face.bbox.astype(int).tolist()
                results.append({
                    "bbox": bbox,
                    "confidence": float(face.det_score),
                    "bbox_in_crop": bbox,
                })
            return results
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []

    def run(self):
        """Main loop — process person crops from queue."""
        self._load_model()
        logger.info("Face detector service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Face detector service received shutdown signal")
                break

            frame_id, camera_id, track_id, person_crop = item
            try:
                faces = self.detect_faces(person_crop)
                self.res_queue.put((frame_id, camera_id, track_id, faces))
            except Exception as e:
                logger.error(f"Face detection failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, track_id, []))

        logger.info("Face detector service stopped")
