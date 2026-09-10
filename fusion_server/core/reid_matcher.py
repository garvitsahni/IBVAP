"""
Cross-Camera Re-ID Matcher - Phase 2 core
Cosine similarity matching with threshold (default 0.75, must be empirically validated)
"""
import numpy as np
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fusion_server.db.models import DetectionEvent


class ReIDMatcher:
    """
    Cross-camera identity matching using cosine similarity on embeddings.
    This is the HIGHEST PRIORITY piece per PHASES.md - must be empirically validated.
    """

    def __init__(self, threshold: float = 0.75, max_candidates: int = 5):
        self.threshold = threshold
        self.max_candidates = max_candidates

    def cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        if emb1 is None or emb2 is None:
            return 0.0
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    def find_matches(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[Tuple[str, np.ndarray]],  # [(object_id, embedding), ...]
    ) -> List[Tuple[str, float]]:
        """
        Find matching identities above threshold.
        Returns list of (object_id, similarity) sorted by similarity descending.
        """
        matches = []
        for obj_id, candidate_emb in candidate_embeddings:
            sim = self.cosine_similarity(query_embedding, candidate_emb)
            if sim >= self.threshold:
                matches.append((obj_id, sim))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:self.max_candidates]

    def get_recent_embeddings(self, db: Session, camera_id: str, since_timestamp: str, limit: int = 100) -> List[Tuple[str, np.ndarray]]:
        """Get recent embeddings from a camera for matching."""
        events = (
            db.query(DetectionEvent)
            .filter(
                DetectionEvent.camera_id == camera_id,
                DetectionEvent.timestamp >= since_timestamp,
                DetectionEvent.embedding.isnot(None),
            )
            .order_by(DetectionEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

        result = []
        for event in events:
            if event.embedding is not None:
                # Convert pgvector to numpy
                emb = np.array(event.embedding, dtype=np.float32)
                result.append((event.track_id, emb))  # Using track_id as provisional object_id
        return result


def match_detection_to_footprint(
    matcher: ReIDMatcher,
    db: Session,
    detection: DetectionEvent,
    all_cameras: List[str],
) -> Optional[str]:
    """
    Match a new detection to existing footprint chains across cameras.
    Returns matched object_id or None if no match (new identity).
    """
    if detection.embedding is None:
        return None

    query_emb = np.array(detection.embedding, dtype=np.float32)

    # Search other cameras for matches
    for cam_id in all_cameras:
        if cam_id == detection.camera_id:
            continue

        # Get recent embeddings from this camera
        candidates = matcher.get_recent_embeddings(db, cam_id, "1970-01-01", limit=50)

        matches = matcher.find_matches(query_emb, candidates)
        if matches:
            return matches[0][0]  # Return best match object_id

    return None