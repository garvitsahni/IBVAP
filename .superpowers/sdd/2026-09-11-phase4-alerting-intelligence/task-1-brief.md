# Task 1: ROI Database Model

**Files:**
- Create: `fusion_server/db/models_roi.py`
- Modify: `fusion_server/db/models.py` (import new model)
- Test: `tests/test_roi_model.py`

**Interfaces:**
- Produces: `ROI` SQLAlchemy model with all fields from spec

## Steps

- [ ] **Step 1: Write the ROI model test**

```python
# tests/test_roi_model.py
"""Tests for ROI database model."""
import pytest
from datetime import datetime
from fusion_server.db.models_roi import ROI


def test_roi_model_fields():
    """ROI model has all required fields."""
    roi = ROI(
        camera_id="cam1",
        name="North Fence",
        polygon=[[0.1, 0.2], [0.3, 0.2], [0.3, 0.4], [0.1, 0.4]],
        alert_on_enter=True,
        alert_on_exit=False,
        object_types=["person", "vehicle"],
        active=True,
    )
    assert roi.camera_id == "cam1"
    assert roi.name == "North Fence"
    assert len(roi.polygon) == 4
    assert roi.alert_on_enter is True
    assert roi.alert_on_exit is False
    assert roi.object_types == ["person", "vehicle"]
    assert roi.active is True


def test_roi_model_defaults():
    """ROI model has correct defaults."""
    roi = ROI(
        camera_id="cam1",
        name="Test",
        polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )
    assert roi.alert_on_enter is True
    assert roi.alert_on_exit is False
    assert roi.object_types is None
    assert roi.active is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_roi_model.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create ROI model**

```python
# fusion_server/db/models_roi.py
"""ROI database model — Phase 4."""
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from fusion_server.db.models import Base
import uuid
from datetime import datetime


class ROI(Base):
    __tablename__ = "roi"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(String(64), nullable=False)  # or '*' for all cameras
    name = Column(String(128), nullable=False)
    polygon = Column(JSON, nullable=False)  # [[x, y], ...] normalized 0-1
    alert_on_enter = Column(Boolean, nullable=False, default=True)
    alert_on_exit = Column(Boolean, nullable=False, default=False)
    object_types = Column(JSON, nullable=True)  # ["person", "vehicle"] or None for all
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_roi_camera_active', 'camera_id', 'active'),
    )
```

- [ ] **Step 4: Add import to models.py**

Add at the bottom of `fusion_server/db/models.py`:
```python
from fusion_server.db.models_roi import ROI  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_roi_model.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add fusion_server/db/models_roi.py fusion_server/db/models.py tests/test_roi_model.py
git commit -m "feat(db): add ROI model for Phase 4 virtual fence"
```
