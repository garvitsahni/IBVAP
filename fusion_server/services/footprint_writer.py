"""
FootprintChainWriter — writes footprint entries with tamper-evident hash chain.
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIN_SAME_CAMERA_GAP = 30


class FootprintChainWriter:
    """Writes footprint chain entries with hash linkage."""

    def __init__(self, min_same_camera_gap: int = MIN_SAME_CAMERA_GAP):
        self.min_same_camera_gap = min_same_camera_gap

    def _compute_hash(
        self,
        object_id: str,
        camera_id: str,
        timestamp: str,
        event_type: str,
        previous_hash: Optional[str],
    ) -> str:
        """Compute SHA-256 hash for footprint entry."""
        data = f"{object_id}{camera_id}{timestamp}{event_type}"
        if previous_hash:
            data += previous_hash
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_last_entry(self, db: Session, object_id: str) -> Optional[Any]:
        """Get the most recent footprint entry for an object."""
        from fusion_server.db.models import FootprintEntry
        entries = (
            db.query(FootprintEntry)
            .filter(FootprintEntry.object_id == object_id)
            .order_by(FootprintEntry.timestamp.desc())
            .limit(1)
            .all()
        )
        return entries[0] if entries else None

    def write_entry(
        self,
        db: Session,
        object_id: str,
        camera_id: str,
        timestamp: datetime,
        event_type: str,
        detection_event_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Write a footprint entry with hash chain linkage.
        Returns entry dict if written, None if skipped.
        """
        from fusion_server.db.models import FootprintEntry

        last_entry = self._get_last_entry(db, object_id)

        if last_entry is not None:
            if last_entry.camera_id == camera_id:
                time_gap = (timestamp - last_entry.timestamp).total_seconds()
                if time_gap < self.min_same_camera_gap:
                    return None
            previous_hash = last_entry.hash
        else:
            previous_hash = None
            if event_type != "first_seen":
                event_type = "first_seen"

        timestamp_str = timestamp.isoformat()
        hash_value = self._compute_hash(
            object_id, camera_id, timestamp_str, event_type, previous_hash
        )

        entry = FootprintEntry(
            object_id=object_id,
            camera_id=camera_id,
            timestamp=timestamp,
            event_type=event_type,
            hash=hash_value,
            previous_hash=previous_hash,
            detection_event_id=detection_event_id,
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        return {
            "id": entry.id,
            "object_id": object_id,
            "camera_id": camera_id,
            "timestamp": timestamp_str,
            "event_type": event_type,
            "hash": hash_value,
            "previous_hash": previous_hash,
        }
