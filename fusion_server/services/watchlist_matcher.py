"""
WatchlistMatcher — compares detection embeddings and plate text against encrypted watchlist.
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
        threshold_face: float = 0.65,
    ):
        self.threshold_person = threshold_person
        self.threshold_plate = threshold_plate
        self.threshold_face = threshold_face
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

    def match_face(
        self,
        db: Session,
        face_embedding: np.ndarray,
    ) -> Optional[Dict]:
        """
        Match a face embedding against face watchlist entries.
        Uses face-specific embedding for higher accuracy.
        Returns {reference_id, similarity, watchlist_type} or None.
        """
        from fusion_server.db.models import Watchlist

        threshold = self.threshold_face
        key = self._get_key()

        entries = (
            db.query(Watchlist)
            .filter(Watchlist.watchlist_type == "face")
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
                similarity = self._cosine_similarity(face_embedding, watchlist_emb)
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "reference_id": entry.reference_id,
                        "similarity": round(similarity, 4),
                        "watchlist_type": "face",
                    }
            except Exception as e:
                logger.warning(f"Failed to decrypt face watchlist entry {entry.id}: {e}")
                continue

        return best_match

    def match_plate_text(
        self,
        db: Session,
        plate_text: str,
    ) -> Optional[Dict]:
        """
        Match detected plate text against plate watchlist entries.
        Uses exact and fuzzy string matching.
        Returns {reference_id, similarity, watchlist_type} or None.
        """
        from fusion_server.db.models import Watchlist

        entries = (
            db.query(Watchlist)
            .filter(Watchlist.watchlist_type == "plate")
            .filter(Watchlist.active == True)
            .all()
        )

        best_match = None
        best_similarity = -1.0
        normalized_plate = plate_text.upper().strip()

        for entry in entries:
            try:
                # Compare against reference_id (plate text stored as reference)
                watchlist_text = entry.reference_id.upper().strip()
                if normalized_plate == watchlist_text:
                    similarity = 1.0
                elif normalized_plate in watchlist_text or watchlist_text in normalized_plate:
                    similarity = 0.8
                else:
                    # Levenshtein-like: character overlap ratio
                    common = sum(1 for a, b in zip(normalized_plate, watchlist_text) if a == b)
                    max_len = max(len(normalized_plate), len(watchlist_text))
                    similarity = common / max_len if max_len > 0 else 0.0

                if similarity >= 0.7 and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "reference_id": entry.reference_id,
                        "similarity": round(similarity, 4),
                        "watchlist_type": "plate",
                    }
            except Exception as e:
                logger.warning(f"Failed to match plate watchlist entry {entry.id}: {e}")
                continue

        return best_match

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
