"""
AlertLedger — hash chain linkage for Alert records.
Alerts form a separate chain from FootprintEntry, keyed by alert_id.
"""
import hashlib
from typing import Optional
from sqlalchemy.orm import Session


class AlertLedger:
    """Manages hash chain for Alert records."""

    @staticmethod
    def compute_alert_hash(
        alert_id: str,
        object_id: str,
        camera_id: str,
        timestamp: str,
        reason: str,
        previous_hash: Optional[str],
    ) -> str:
        """Compute SHA-256 hash for alert entry."""
        data = f"{alert_id}{object_id}{camera_id}{timestamp}{reason}"
        if previous_hash:
            data += previous_hash
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_last_alert_hash(self, db: Session) -> Optional[str]:
        """Get the hash of the most recent alert."""
        from fusion_server.db.models import Alert
        last = (
            db.query(Alert)
            .filter(Alert.hash.isnot(None))
            .order_by(Alert.created_at.desc())
            .limit(1)
            .first()
        )
        return last.hash if last else None

    def write_alert_with_hash(self, db: Session, alert) -> None:
        """Compute and set hash chain for an alert, then commit."""
        previous_hash = self._get_last_alert_hash(db)

        timestamp_str = alert.timestamp.replace(tzinfo=None).isoformat()
        hash_value = self.compute_alert_hash(
            alert.alert_id,
            alert.object_id,
            alert.camera_id,
            timestamp_str,
            alert.reason,
            previous_hash,
        )

        alert.hash = hash_value
        alert.previous_hash = previous_hash
        db.commit()
        db.refresh(alert)
