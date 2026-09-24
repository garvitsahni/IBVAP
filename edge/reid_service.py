"""
Re-ID Service — extracts person/vehicle embeddings from detection crops.
Runs as a separate process, receives crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Standard Re-ID input sizes
REID_INPUT_HEIGHT = 256
REID_INPUT_WIDTH = 128
# Vehicle Re-ID (VeRi-776) input size
VEHICLE_REID_HEIGHT = 256
VEHICLE_REID_WIDTH = 256
# ImageNet normalization for VeRi-776
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)


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
        """Load ONNX model for inference (GPU-primary, loud fallback)."""
        try:
            from edge.model_runtime import create_session
            self._session = create_session(self.model_path)
            self._input_name = self._session.get_inputs()[0].name
            inp = self._session.get_inputs()[0]
            self._input_h, self._input_w = inp.shape[2], inp.shape[3]
        except RuntimeError as e:
            logger.warning(f"{e}")
            logger.warning("ReID service will return None embeddings (graceful fallback)")
            self._session = None
            self._input_h, self._input_w = REID_INPUT_HEIGHT, REID_INPUT_WIDTH
        except Exception as e:
            logger.warning(f"Failed to load ReID model from {self.model_path}: {e}")
            logger.warning("ReID service will return None embeddings (graceful fallback)")
            self._session = None
            self._input_h, self._input_w = REID_INPUT_HEIGHT, REID_INPUT_WIDTH

    def _load_vehicle_model(self):
        """Load ONNX model for vehicle Re-ID inference (GPU-primary, loud fallback)."""
        try:
            from edge.model_runtime import create_session
            self._vehicle_session = create_session(self.vehicle_model_path)
            self._vehicle_input_name = self._vehicle_session.get_inputs()[0].name
            inp = self._vehicle_session.get_inputs()[0]
            self._vehicle_input_h, self._vehicle_input_w = inp.shape[2], inp.shape[3]
        except RuntimeError as e:
            logger.warning(f"{e}")
            self._vehicle_session = None
            self._vehicle_input_h, self._vehicle_input_w = VEHICLE_REID_HEIGHT, VEHICLE_REID_WIDTH
        except Exception as e:
            logger.warning(f"Failed to load vehicle ReID model: {e}")
            self._vehicle_session = None
            self._vehicle_input_h, self._vehicle_input_w = VEHICLE_REID_HEIGHT, VEHICLE_REID_WIDTH

    def _preprocess_crop(
        self,
        crop: np.ndarray,
        target_h: int = REID_INPUT_HEIGHT,
        target_w: int = REID_INPUT_WIDTH,
        is_vehicle: bool = False,
    ) -> np.ndarray:
        """
        Preprocess crop for Re-ID inference.
        Input: BGR numpy array (H, W, 3) uint8
        Output: NCHW float32 array normalized
        - Person (OSNet): [0, 1]
        - Vehicle (VeRi-776): ImageNet mean/std normalization
        """
        import cv2
        resized = cv2.resize(crop, (target_w, target_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)  # HWC -> CHW (before mean/std: shapes (3,1,1))
        if is_vehicle:
            # ImageNet normalization for VeRi-776
            blob = (blob - IMAGENET_MEAN) / IMAGENET_STD
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
            if is_vehicle:
                target_h, target_w = self._vehicle_input_h, self._vehicle_input_w
            else:
                target_h, target_w = self._input_h, self._input_w
            blob = self._preprocess_crop(crop, target_h, target_w, is_vehicle=is_vehicle)
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
