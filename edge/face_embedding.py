"""
Face Embedding Service — extracts ArcFace embeddings from detected face crops.
Runs as a separate process, receives face crops via multiprocessing.Queue.
"""
import numpy as np
import multiprocessing
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Standard ArcFace input size
FACE_EMBED_INPUT_SIZE = 112


class FaceEmbeddingService:
    """
    Face embedding extraction service using ArcFace (InsightFace).

    Usage:
        req_queue = multiprocessing.Queue()
        res_queue = multiprocessing.Queue()
        svc = FaceEmbeddingService(req_queue, res_queue)
        svc.run()  # blocking loop
    """

    def __init__(
        self,
        req_queue: multiprocessing.Queue,
        res_queue: multiprocessing.Queue,
        model_path: str = "models/arcface_r100.onnx",
    ):
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.model_path = model_path
        self._session = None
        self._input_name = None
        self._input_size = FACE_EMBED_INPUT_SIZE

    def _load_model(self):
        """Load ONNX model for ArcFace inference."""
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(
                self.model_path,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            logger.info(f"Face embedding model loaded from {self.model_path}")
        except FileNotFoundError:
            logger.warning(
                f"Face embedding model not found at {self.model_path}. "
                "Face embeddings will not be available."
            )
            self._session = None
        except Exception as e:
            logger.warning(f"Failed to load face embedding model: {e}")
            self._session = None

    def _preprocess_face(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Preprocess face crop for ArcFace inference.
        Input: BGR numpy array (H, W, 3) uint8
        Output: NCHW float32 array normalized to [-1, 1]
        """
        import cv2
        resized = cv2.resize(
            face_crop,
            (self._input_size, self._input_size),
            interpolation=cv2.INTER_LINEAR,
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32)
        # Normalize to [-1, 1] (ArcFace standard preprocessing)
        blob = (blob - 127.5) / 128.0
        blob = blob.transpose(2, 0, 1)  # HWC -> CHW
        blob = np.expand_dims(blob, 0)  # Add batch dimension
        return blob

    def extract_embedding(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract 512-dim ArcFace embedding from a face crop.
        Returns None if model is not available or inference fails.
        """
        if self._session is None:
            return None

        try:
            blob = self._preprocess_face(face_crop)
            outputs = self._session.run(None, {self._input_name: blob})
            embedding = outputs[0].flatten()
            # Normalize to unit vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            logger.error(f"Face embedding inference failed: {e}")
            return None

    def run(self):
        """Main loop — process face crops from queue."""
        self._load_model()
        logger.info("Face embedding service started")

        while True:
            try:
                item = self.req_queue.get(timeout=1.0)
            except Exception:
                continue

            if item is None:
                logger.info("Face embedding service received shutdown signal")
                break

            frame_id, camera_id, track_id, face_crop = item
            try:
                embedding = self.extract_embedding(face_crop)
                self.res_queue.put((frame_id, camera_id, track_id, embedding))
            except Exception as e:
                logger.error(f"Face embedding failed for {camera_id}/{frame_id}: {e}")
                self.res_queue.put((frame_id, camera_id, track_id, None))

        logger.info("Face embedding service stopped")
