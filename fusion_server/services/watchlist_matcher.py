"""
WatchlistMatcher — compares detection embeddings against encrypted watchlist.
"""
import numpy as np
import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session

from fusion_server.core.watchlist_crypto import decrypt_embedding, get_key

logger = logging.getLogger(__name__)


class WatchlistMatcher:
    """Matches detection embeddings against watchlist entries."""

    def __init__(
        self,
        threshold_person: float = 0.70,
        threshold_plate: float = 0.65,
    ):
        self.threshold_person = threshold_person
        self.threshold_plate = threshold_plate
        self._key = None

    def _get_key(self) -> bytes:
        if self._key is None:
            self._key = get_key()
        return self._key

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _get_threshold(self, object_type: str) -> float:
        if object_type == "vehicle":
            return self.threshold_plate
        return self.threshold_person

    def match_detection(
        self,
        db: Session,
        embedding: np.ndarray,
        object_type: str,
    ) -> Optional[Dict]:
        """
        Match a detection embedding against the watchlist.
        Returns {reference_id, similarity, watchlist_type} or None.
        """
        from fusion_server.db.models import Watchlist

        threshold = self._get_threshold(object_type)
        key = self._get_key()

        # Determine watchlist type from object_type
        watchlist_type = "face" if object_type == "person" else "plate"

        entries = (
            db.query(Watchlist)
            .filter(Watchlist.watchlist_type == watchlist_type)
            .filter(Watchlist.active == True)
            .all()
        )

        best_match = None
        best_similarity = -1.0

        for entry in entries:
            try:
                watchlist_emb = np.array(
                    decrypt_embedding(entry.embedding, key),
                    dtype=np.float32,
                )
                similarity = self._cosine_similarity(embedding, watchlist_emb)
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "reference_id": entry.reference_id,
                        "similarity": round(similarity, 4),
                        "watchlist_type": watchlist_type,
                    }
            except Exception as e:
                logger.warning(f"Failed to decrypt watchlist entry {entry.id}: {e}")
                continue

        return best_match
