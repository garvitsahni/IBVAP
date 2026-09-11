### Task 5: MatchingEngine — pgvector Cosine Search

**Files:**
- Create: `fusion_server/services/__init__.py`
- Create: `fusion_server/services/matching_engine.py`
- Create: `tests/test_matching_engine.py`

**Interfaces:**
- Consumes: DetectionEvent with embedding from POST /api/v1/events
- Produces: assigned `object_id` (existing or new UUID)

- [ ] **Step 1: Write the failing test**

Create `tests/test_matching_engine.py`:
```python
"""Tests for MatchingEngine — pgvector cosine similarity matching."""
import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def test_matching_engine_initializes():
    """MatchingEngine can be instantiated."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.65, threshold_vehicle=0.60)
    assert engine.threshold_person == 0.65
    assert engine.threshold_vehicle == 0.60


def test_matching_engine_cosine_similarity():
    """MatchingEngine computes cosine similarity correctly."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(1.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(0.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([-1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(-1.0)


def test_matching_engine_new_object():
    """MatchingEngine creates new object_id when no match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime.utcnow(),
    )

    assert object_id is not None
    assert len(object_id) > 0


def test_matching_engine_existing_match():
    """MatchingEngine returns existing object_id when match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.5)  # Low threshold for test

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    mock_event = MagicMock()
    mock_event.object_id = "existing-object-123"
    mock_event.embedding = embedding.tolist()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_event]

    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime.utcnow(),
    )

    assert object_id == "existing-object-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\activate; pytest tests/test_matching_engine.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'fusion_server.services'`)

- [ ] **Step 3: Write minimal implementation**

Create `fusion_server/services/__init__.py`:
```python
# Phase 2 services
```

Create `fusion_server/services/matching_engine.py`:
```python
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
from sqlalchemy import text

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
            result = db.execute(
                text("""
                    SELECT object_id, embedding <=> :query_embedding AS distance
                    FROM detection_events
                    WHERE object_type = :object_type
                      AND timestamp >= :cutoff
                      AND embedding IS NOT NULL
                      AND object_id IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT 5
                """),
                {
                    "query_embedding": embedding.tolist(),
                    "object_type": object_type,
                    "cutoff": cutoff,
                },
            )

            rows = result.fetchall()

            for row in rows:
                similarity = 1.0 - row.distance
                if similarity >= threshold:
                    logger.debug(f"Matched to existing object {row.object_id} (sim={similarity:.3f})")
                    return row.object_id

        except Exception as e:
            logger.warning(f"pgvector query failed, falling back to new object: {e}")

        new_object_id = str(uuid.uuid4())
        logger.debug(f"Created new object {new_object_id}")
        return new_object_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\activate; pytest tests/test_matching_engine.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/ tests/test_matching_engine.py
git commit -m "Phase 2: add MatchingEngine with pgvector cosine search"
```
