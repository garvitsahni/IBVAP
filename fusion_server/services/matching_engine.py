"""
MatchingEngine — assigns global object_ids to detections via pgvector cosine search.
Runs asynchronously after event ingestion.
"""
import numpy as np
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from fusion_server.db.models import DetectionEvent

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Cross-camera re-identification matching engine.
    Uses pgvector cosine search to find matching embeddings.
    """

    def __init__(
        self,
        threshold_person: float = 0.65,
        threshold_vehicle: float = 0.60,
        time_window_minutes: int = 5,
    ):
        self.threshold_person = threshold_person
        self.threshold_vehicle = threshold_vehicle
        self.time_window_minutes = time_window_minutes

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _get_threshold(self, object_type: str) -> float:
        """Get matching threshold for object type."""
        if object_type == "person":
            return self.threshold_person
        return self.threshold_vehicle

    def match_or_create(
        self,
        db: Session,
        embedding: np.ndarray,
        object_type: str,
        camera_id: str,
        timestamp: datetime,
    ) -> str:
        """
        Find matching object or create new one.
        Returns object_id (existing or newly generated UUID).
        """
        threshold = self._get_threshold(object_type)
        cutoff = timestamp - timedelta(minutes=self.time_window_minutes)

        try:
            results = (
                db.query(DetectionEvent)
                .filter(DetectionEvent.object_type == object_type)
                .filter(DetectionEvent.timestamp >= cutoff)
                .all()
            )

            best_match_id = None
            best_similarity = -1.0

            for row in results:
                if row.embedding is None or not hasattr(row, 'object_id') or row.object_id is None:
                    continue
                row_embedding = np.array(row.embedding, dtype=np.float32)
                similarity = self._cosine_similarity(embedding, row_embedding)
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match_id = row.object_id

            if best_match_id is not None:
                logger.debug(f"Matched to existing object {best_match_id} (sim={best_similarity:.3f})")
                return best_match_id

        except Exception as e:
            logger.warning(f"Query failed, falling back to new object: {e}")

        new_object_id = str(uuid.uuid4())
        logger.debug(f"Created new object {new_object_id}")
        return new_object_id
