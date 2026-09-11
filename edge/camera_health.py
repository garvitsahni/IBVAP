"""
Camera Health Service — monitors camera tamper/drift via SSIM and scene embeddings.
"""
import numpy as np
import logging
from typing import Optional, Dict
from collections import deque

logger = logging.getLogger(__name__)


class CameraHealthService:
    def __init__(
        self,
        camera_id: str,
        tamper_threshold: float = 0.1,
        drift_threshold: float = 0.3,
        scene_drift_threshold: float = 0.3,
        max_scene_embeddings: int = 100,
    ):
        self.camera_id = camera_id
        self.tamper_threshold = tamper_threshold
        self.drift_threshold = drift_threshold
        self.scene_drift_threshold = scene_drift_threshold
        self._reference_frame: Optional[np.ndarray] = None
        self._scene_embeddings: deque = deque(maxlen=max_scene_embeddings)
        self._scene_centroid: Optional[np.ndarray] = None

    def set_reference_frame(self, frame: np.ndarray):
        self._reference_frame = frame.copy()

    def set_scene_embedding(self, embedding: np.ndarray):
        self._scene_centroid = embedding.copy()
        self._scene_embeddings.clear()
        self._scene_embeddings.append(embedding.copy())

    def update_scene_embedding(self, embedding: np.ndarray):
        self._scene_embeddings.append(embedding.copy())
        if len(self._scene_embeddings) > 0:
            self._scene_centroid = np.mean(list(self._scene_embeddings), axis=0)
            norm = np.linalg.norm(self._scene_centroid)
            if norm > 0:
                self._scene_centroid = self._scene_centroid / norm

    def compute_ssim(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        try:
            from skimage.metrics import structural_similarity as ssim
            if len(frame1.shape) == 3:
                gray1 = np.mean(frame1, axis=2).astype(np.uint8)
                gray2 = np.mean(frame2, axis=2).astype(np.uint8)
            else:
                gray1, gray2 = frame1, frame2
            return float(ssim(gray1, gray2, data_range=255))
        except ImportError:
            diff = np.mean(np.abs(frame1.astype(float) - frame2.astype(float)))
            return max(0.0, 1.0 - diff / 128.0)

    def check_health(self, live_frame: np.ndarray) -> Dict:
        if self._reference_frame is None:
            return {"status": "unknown", "ssim": 0.0, "message": "No reference frame set"}
        if live_frame.shape != self._reference_frame.shape:
            import cv2
            live_frame = cv2.resize(live_frame, (self._reference_frame.shape[1], self._reference_frame.shape[0]))
        ssim_score = self.compute_ssim(self._reference_frame, live_frame)
        if ssim_score < self.tamper_threshold:
            status = "tamper"
        elif ssim_score < self.drift_threshold:
            status = "drift"
        else:
            status = "ok"
        return {"status": status, "ssim": round(ssim_score, 4)}

    def check_scene_drift(self, embedding: np.ndarray) -> Dict:
        if self._scene_centroid is None:
            return {"scene_drift": False, "similarity": 0.0}
        similarity = float(np.dot(embedding, self._scene_centroid) / (
            np.linalg.norm(embedding) * np.linalg.norm(self._scene_centroid)
        ))
        scene_drift = similarity < self.scene_drift_threshold
        return {"scene_drift": scene_drift, "similarity": round(similarity, 4)}

    def check_darkness(self, frame: np.ndarray) -> Dict:
        """Detect full-frame darkness (blinding). Returns mean pixel intensity."""
        if len(frame.shape) == 3:
            gray = np.mean(frame, axis=2)
        else:
            gray = frame.astype(float)
        mean_intensity = float(np.mean(gray))
        status = "blinding" if mean_intensity < 15 else "ok"
        return {"status": status, "metric": round(mean_intensity, 2)}

    def check_blur(self, frame: np.ndarray) -> Dict:
        """Detect blur/obscuration via Laplacian variance."""
        import cv2
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        status = "obscured" if laplacian_var < 50 else "ok"
        return {"status": status, "metric": round(laplacian_var, 2)}

    def check_frozen(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> Dict:
        """Detect frozen frame via mean absolute difference."""
        diff = float(np.mean(np.abs(prev_frame.astype(float) - curr_frame.astype(float))))
        status = "frozen" if diff < 1.0 else "ok"
        return {"status": status, "metric": round(diff, 2)}
