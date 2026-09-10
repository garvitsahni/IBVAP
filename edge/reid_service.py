"""
Re-ID Service — extracts person/vehicle embeddings from detection crops.
Runs as a separate process, receives crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Standard Re-ID input size
REID_INPUT_HEIGHT = 256
REID_INPUT_WIDTH = 128


class ReIDService:
    """
    Re-ID embedding extraction service.

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = ReIDService(req_queue, res_queue, model_path="models/osnet_ain_x1_0.onnx")
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "models/osnet_ain_x1_0.onnx",
        vehicle_model_path: str = "models/vehicle_reid.onnx",
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self.vehicle_model_path = vehicle_model_path
        self._session = None
        self._input_name = None
        self._vehicle_session = None
        self._vehicle_input_name = None

    def _load_model(self):
        """Load ONNX model for inference."""
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(self.model_path)
            self._input_name = self._session.get_inputs()[0].name
            logger.info(f"ReID model loaded from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load ReID model from {self.model_path}: {e}")
            logger.warning("ReID service will return None embeddings (graceful fallback)")
            self._session = None

    def _load_vehicle_model(self):
        """Load ONNX model for vehicle Re-ID inference."""
        try:
            import onnxruntime as ort
            self._vehicle_session = ort.InferenceSession(self.vehicle_model_path)
            self._vehicle_input_name = self._vehicle_session.get_inputs()[0].name
            logger.info(f"Vehicle ReID model loaded from {self.vehicle_model_path}")
        except Exception as e:
            logger.warning(f"Failed to load vehicle ReID model: {e}")
            self._vehicle_session = None

    def _preprocess_crop(self, crop: np.ndarray) -> np.ndarray:
        """
        Preprocess crop for Re-ID inference.
        Input: BGR numpy array (H, W, 3) uint8
        Output: NCHW float32 array normalized to [0, 1]
        """
        import cv2
        # Resize to standard Re-ID input size
        resized = cv2.resize(crop, (REID_INPUT_WIDTH, REID_INPUT_HEIGHT))
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Normalize to [0, 1] and transpose to NCHW
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)  # HWC -> CHW
        blob = np.expand_dims(blob, 0)  # Add batch dimension
        return blob

    def extract_embedding(self, crop: np.ndarray, is_vehicle: bool = False) -> Optional[np.ndarray]:
        """
        Extract 512-dim embedding from a crop.
        Returns None if model is not available.
        """
        session = self._vehicle_session if is_vehicle else self._session
        input_name = self._vehicle_input_name if is_vehicle else self._input_name

        if session is None:
            return None

        try:
            blob = self._preprocess_crop(crop)
            outputs = session.run(None, {input_name: blob})
            embedding = outputs[0].flatten()
            # Normalize to unit vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            logger.error(f"ReID inference failed: {e}")
            return None

    def _process_one(self):
        """Process one item from the request queue."""
        try:
            item = self.req_queue.get(timeout=0.1)
        except Exception:
            return

        if item is None:
            return

        frame_id, camera_id, track_id, crop, object_type = item
        is_vehicle = object_type == "vehicle"
        embedding = self.extract_embedding(crop, is_vehicle=is_vehicle)
        self.res_queue.put((frame_id, camera_id, track_id, embedding, object_type))

    def run(self):
        """Main loop — process crops from queue."""
        self._load_model()
        self._load_vehicle_model()
        logger.info("ReID service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("ReID service received shutdown signal")
                break

            frame_id, camera_id, track_id, crop, object_type = item
            try:
                is_vehicle = object_type == "vehicle"
                embedding = self.extract_embedding(crop, is_vehicle=is_vehicle)
                self.res_queue.put((frame_id, camera_id, track_id, embedding, object_type))
            except Exception as e:
                logger.error(f"ReID failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, track_id, None, object_type))

        logger.info("ReID service stopped")
