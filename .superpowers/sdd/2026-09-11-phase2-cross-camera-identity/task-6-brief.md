### Task 6: FootprintChainWriter — Hash Chain Logic

**Files:**
- Create: `fusion_server/services/footprint_writer.py`
- Create: `tests/test_footprint_writer.py`

**Interfaces:**
- Consumes: object_id, camera_id, timestamp, detection_event_id
- Produces: FootprintEntry records with hash chain linkage

- [ ] **Step 1: Write the failing test**

Create `tests/test_footprint_writer.py`:
```python
"""Tests for FootprintChainWriter — footprint chain with hash linkage."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_footprint_writer_initializes():
    """FootprintChainWriter can be instantiated."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()
    assert writer is not None


def test_footprint_writer_first_seen():
    """FootprintChainWriter creates first_seen entry for new object."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
        event_type="first_seen",
        detection_event_id=1,
    )

    assert entry is not None
    assert entry["event_type"] == "first_seen"
    assert entry["previous_hash"] is None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_footprint_writer_hop_different_camera():
    """FootprintChainWriter creates hop entry when camera changes."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.event_type = "first_seen"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_last_entry]

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
        event_type="hop",
        detection_event_id=2,
    )

    assert entry is not None
    assert entry["event_type"] == "hop"
    assert entry["previous_hash"] == "abc123"


def test_footprint_writer_same_camera_no_hop():
    """FootprintChainWriter skips hop when same camera and recent."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.timestamp = datetime(2026, 9, 11, 10, 0, 0)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_last_entry]

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 1),
        event_type="hop",
        detection_event_id=3,
    )

    assert entry is None
    mock_db.add.assert_not_called()


def test_footprint_writer_hash_chain():
    """FootprintChainWriter computes hash correctly."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    hash_value = writer._compute_hash(
        object_id="obj-123",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        event_type="first_seen",
        previous_hash=None,
    )

    assert hash_value is not None
    assert len(hash_value) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_footprint_writer.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'fusion_server.services.footprint_writer'`)

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/footprint_writer.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_footprint_writer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/footprint_writer.py tests/test_footprint_writer.py
git commit -m "Phase 2: add FootprintChainWriter with hash chain linkage"
```
