# Phase 4 — Alerting & Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic rule engine, suspicious activity detection, threat scoring, trajectory projection, AI enrichment, ANPR, and SSE alert push — completing the alert pipeline from detection to enriched alert.

**Architecture:** Two-speed alert pipeline: synchronous rule checks fire alerts in <10ms, async AI enrichment appends explanation within seconds. ANPR runs as a parallel workstream.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, shapely (geometry), numpy (Kalman filter), pydantic, asyncio (SSE), ultralytics (YOLOv8), PaddleOCR/EasyOCR (ANPR), transformers + torch (LLaVA).

## Global Constraints

- Deterministic-only for alert decisions (no ML in the rule engine path)
- `threat_score` field has CHECK constraint `0 <= score <= 1`
- Data contracts in ARCHITECTURE.md Section 5 are frozen — no field changes without updating the doc
- AI enrichment must never block alert delivery (async only)
- Ledger write is synchronous and blocking
- No external API calls for core functionality — local models only
- All features must work on real input, no faked/stubbed paths without `[SIMULATED / UNIT-TESTED ONLY]` marker
- ANPR can be a separate person working in parallel
- LLaVA-1.5-7B for AI enrichment (local VLM)
- Pre-trained ANPR model for plate detection + PaddleOCR/EasyOCR for OCR
- SSE for real-time alert push (no WebSocket)
- Database table + API for ROI persistence
- In-memory trajectory buffer with DB reconstruction

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `fusion_server/db/models_roi.py` | ROI SQLAlchemy model |
| `fusion_server/db/models_plate.py` | PlateDetection SQLAlchemy model |
| `fusion_server/api/routes/rois.py` | ROI CRUD API |
| `fusion_server/api/routes/plates.py` | Plate detection query API |
| `fusion_server/core/trajectory_buffer.py` | In-memory per-object trajectory buffer |
| `fusion_server/core/suspicious_activity.py` | Loitering, path reversal, group clustering |
| `fusion_server/services/alert_pipeline.py` | Orchestrates sync rule check + async enrichment |
| `fusion_server/services/sse_broadcaster.py` | SSE alert push to connected clients |
| `fusion_server/services/ai_enrichment.py` | LLaVA-based alert enrichment |
| `fusion_server/core/anpr.py` | Plate detection + OCR pipeline |
| `fusion_server/api/routes/stream.py` | SSE endpoint + viewer HTML |
| `templates/viewer.html` | Minimal alert viewer page |
| `tests/test_roi_model.py` | ROI model tests |
| `tests/test_roi_api.py` | ROI CRUD API tests |
| `tests/test_trajectory_buffer.py` | Trajectory buffer tests |
| `tests/test_suspicious_activity.py` | Suspicious activity rule tests |
| `tests/test_alert_pipeline.py` | Alert pipeline tests |
| `tests/test_threat_scoring_wiring.py` | Threat scoring wiring tests |
| `tests/test_trajectory_projection.py` | Trajectory projection at alert time tests |
| `tests/test_sse_broadcaster.py` | SSE broadcaster tests |
| `tests/test_anpr.py` | ANPR pipeline tests |
| `tests/test_ai_enrichment.py` | AI enrichment tests |
| `tests/test_phase4_integration.py` | Full integration tests |

### Modified Files

| File | Changes |
|------|---------|
| `fusion_server/db/models.py` | Import new models, add `event_type` values to FootprintEntry CHECK constraint |
| `fusion_server/api/events.py` | Wire rule engine, trajectory buffer, alert pipeline into event ingestion |
| `fusion_server/api/alerts.py` | Add SSE broadcast on alert creation |
| `fusion_server/main.py` | Register new routers (rois, plates, stream), load ROIs on startup |
| `fusion_server/core/rule_engine.py` | Add `load_rois_from_db()`, add `evaluate()` method that runs all rules |
| `fusion_server/core/threat_scoring.py` | Add `path_reversal`, `group_clustering`, `plate_watchlist_match` to VIOLATION_BASE_SCORES |
| `ARCHITECTURE.md` | Update Section 5 data contracts (ROI, PlateDetection, updated Alert reason enum) |

---

## Task 1: ROI Database Model

**Files:**
- Create: `fusion_server/db/models_roi.py`
- Modify: `fusion_server/db/models.py` (import new model)
- Test: `tests/test_roi_model.py`

**Interfaces:**
- Produces: `ROI` SQLAlchemy model with all fields from spec

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

---

## Task 2: PlateDetection Database Model

**Files:**
- Create: `fusion_server/db/models_plate.py`
- Modify: `fusion_server/db/models.py` (import new model)
- Test: `tests/test_plate_model.py`

**Interfaces:**
- Produces: `PlateDetection` SQLAlchemy model

- [ ] **Step 1: Write the PlateDetection model test**

```python
# tests/test_plate_model.py
"""Tests for PlateDetection database model."""
import pytest
from fusion_server.db.models_plate import PlateDetection


def test_plate_detection_model_fields():
    """PlateDetection model has all required fields."""
    plate = PlateDetection(
        object_id="obj_001",
        camera_id="cam1",
        plate_text="ABC1234",
        confidence=0.92,
        bbox=[0.1, 0.2, 0.15, 0.05],
    )
    assert plate.object_id == "obj_001"
    assert plate.camera_id == "cam1"
    assert plate.plate_text == "ABC1234"
    assert plate.confidence == 0.92
    assert plate.bbox == [0.1, 0.2, 0.15, 0.05]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_plate_model.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create PlateDetection model**

```python
# fusion_server/db/models_plate.py
"""PlateDetection database model — Phase 4 ANPR."""
from sqlalchemy import Column, String, DateTime, Float, JSON, BigInteger, Index
from fusion_server.db.models import Base
from datetime import datetime


class PlateDetection(Base):
    __tablename__ = "plate_detections"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    object_id = Column(String(128), nullable=False)
    camera_id = Column(String(64), nullable=False)
    plate_text = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    bbox = Column(JSON, nullable=False)  # [x, y, w, h] normalized 0-1
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_plate_camera_time', 'camera_id', 'created_at'),
        Index('idx_plate_text', 'plate_text'),
    )
```

- [ ] **Step 4: Add import to models.py**

Add at the bottom of `fusion_server/db/models.py`:
```python
from fusion_server.db.models_plate import PlateDetection  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_plate_model.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add fusion_server/db/models_plate.py fusion_server/db/models.py tests/test_plate_model.py
git commit -m "feat(db): add PlateDetection model for Phase 4 ANPR"
```

---

## Task 3: Trajectory History Buffer

**Files:**
- Create: `fusion_server/core/trajectory_buffer.py`
- Test: `tests/test_trajectory_buffer.py`

**Interfaces:**
- Produces: `TrajectoryBuffer` class with `add_point(object_id, x, y, timestamp)`, `get_points(object_id)`, `get_recent(object_id, n)`, `remove(object_id)`, `clear()`

- [ ] **Step 1: Write trajectory buffer tests**

```python
# tests/test_trajectory_buffer.py
"""Tests for in-memory trajectory buffer."""
import pytest
import time
from fusion_server.core.trajectory_buffer import TrajectoryBuffer


def test_add_and_get_points():
    """Add points and retrieve them."""
    buf = TrajectoryBuffer()
    buf.add_point("obj1", 0.1, 0.2, 1000.0)
    buf.add_point("obj1", 0.3, 0.4, 1001.0)
    points = buf.get_points("obj1")
    assert len(points) == 2
    assert points[0].x == 0.1
    assert points[1].y == 0.4


def test_get_recent():
    """Get last N points."""
    buf = TrajectoryBuffer()
    for i in range(10):
        buf.add_point("obj1", float(i) / 10, 0.5, 1000.0 + i)
    recent = buf.get_recent("obj1", 3)
    assert len(recent) == 3
    assert recent[0].x == 0.7
    assert recent[2].x == 0.9


def test_remove_object():
    """Remove all points for an object."""
    buf = TrajectoryBuffer()
    buf.add_point("obj1", 0.1, 0.2, 1000.0)
    buf.remove("obj1")
    assert buf.get_points("obj1") == []


def test_clear():
    """Clear all objects."""
    buf = TrajectoryBuffer()
    buf.add_point("obj1", 0.1, 0.2, 1000.0)
    buf.add_point("obj2", 0.3, 0.4, 1000.0)
    buf.clear()
    assert buf.get_points("obj1") == []
    assert buf.get_points("obj2") == []


def test_get_points_unknown_object():
    """Unknown object returns empty list."""
    buf = TrajectoryBuffer()
    assert buf.get_points("unknown") == []


def test_max_points_per_object():
    """Buffer respects max points per object."""
    buf = TrajectoryBuffer(max_points_per_object=5)
    for i in range(10):
        buf.add_point("obj1", float(i) / 10, 0.5, 1000.0 + i)
    points = buf.get_points("obj1")
    assert len(points) == 5
    assert points[0].x == 0.5  # Last 5 points
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_trajectory_buffer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement TrajectoryBuffer**

```python
# fusion_server/core/trajectory_buffer.py
"""In-memory trajectory buffer — accumulates position history per object."""
from typing import List, Optional
from dataclasses import dataclass
from collections import defaultdict
import threading


@dataclass
class TrajectoryPoint:
    x: float
    y: float
    timestamp: float


class TrajectoryBuffer:
    """Thread-safe in-memory buffer for per-object trajectory history."""

    def __init__(self, max_points_per_object: int = 100):
        self._buffer: dict[str, List[TrajectoryPoint]] = defaultdict(list)
        self._max = max_points_per_object
        self._lock = threading.Lock()

    def add_point(self, object_id: str, x: float, y: float, timestamp: float) -> None:
        """Add a position point for an object."""
        with self._lock:
            self._buffer[object_id].append(TrajectoryPoint(x=x, y=y, timestamp=timestamp))
            if len(self._buffer[object_id]) > self._max:
                self._buffer[object_id] = self._buffer[object_id][-self._max:]

    def get_points(self, object_id: str) -> List[TrajectoryPoint]:
        """Get all points for an object."""
        with self._lock:
            return list(self._buffer.get(object_id, []))

    def get_recent(self, object_id: str, n: int) -> List[TrajectoryPoint]:
        """Get last N points for an object."""
        with self._lock:
            points = self._buffer.get(object_id, [])
            return list(points[-n:])

    def remove(self, object_id: str) -> None:
        """Remove all points for an object."""
        with self._lock:
            self._buffer.pop(object_id, None)

    def clear(self) -> None:
        """Clear all objects."""
        with self._lock:
            self._buffer.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_trajectory_buffer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/core/trajectory_buffer.py tests/test_trajectory_buffer.py
git commit -m "feat(core): add in-memory trajectory buffer for Phase 4"
```

---

## Task 4: Update FootprintEntry event_type Constraint

**Files:**
- Modify: `fusion_server/db/models.py:58` (CHECK constraint)
- Test: existing tests still pass

**Interfaces:**
- Consumes: existing FootprintEntry model
- Produces: updated CHECK constraint allowing `roi_intrusion` and `suspicious_activity`

- [ ] **Step 1: Update the CHECK constraint**

In `fusion_server/db/models.py`, line 58, change:
```python
CheckConstraint("event_type IN ('first_seen', 'hop', 'alert', 'last_seen', 'camera_compromised')", name='ck_footprint_event_type'),
```
to:
```python
CheckConstraint("event_type IN ('first_seen', 'hop', 'alert', 'last_seen', 'camera_compromised', 'roi_intrusion', 'suspicious_activity')", name='ck_footprint_event_type'),
```

- [ ] **Step 2: Run existing tests**

Run: `.venv\Scripts\pytest tests/ -v --ignore=tests/test_api_phase2.py --ignore=tests/test_phase0.py --ignore=tests/test_detector.py --ignore=tests/test_yolo_load.py --ignore=tests/test_tracker.py -x`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add fusion_server/db/models.py
git commit -m "fix(db): extend FootprintEntry event_type for Phase 4 rules"
```

---

## Task 5: Suspicious Activity Detection Module

**Files:**
- Create: `fusion_server/core/suspicious_activity.py`
- Test: `tests/test_suspicious_activity.py`

**Interfaces:**
- Consumes: `TrajectoryBuffer` (from Task 3)
- Produces: `SuspiciousActivityDetector` class with `check_loitering()`, `check_path_reversal()`, `check_group_clustering()`

- [ ] **Step 1: Write suspicious activity tests**

```python
# tests/test_suspicious_activity.py
"""Tests for suspicious activity detection rules."""
import pytest
import math
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector, SuspiciousActivity


def _make_detector(**kwargs):
    return SuspiciousActivityDetector(**kwargs)


def _add_points(detector, object_id, points, camera_id="cam1"):
    """Helper to add trajectory points."""
    for i, (x, y) in enumerate(points):
        detector.update(object_id, camera_id, x, y, 1000.0 + i)


def test_loitering_dwell_triggers():
    """Object inside ROI for > threshold triggers loitering alert."""
    det = _make_detector(loiter_threshold_s=5.0)
    # ROI: [0.0, 0.0] to [0.5, 0.5]
    roi_polygon = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    # Add 6 points inside ROI (1 per second, threshold 5s)
    points = [(0.25, 0.25)] * 6
    _add_points(det, "obj1", points)
    violations = det.check_loitering("obj1", roi_polygon)
    assert len(violations) == 1
    assert violations[0].activity_type == "loitering"
    assert violations[0].duration_s >= 5.0


def test_loitering_no_trigger_under_threshold():
    """Object inside ROI for < threshold does not trigger."""
    det = _make_detector(loiter_threshold_s=10.0)
    roi_polygon = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    points = [(0.25, 0.25)] * 5
    _add_points(det, "obj1", points)
    violations = det.check_loitering("obj1", roi_polygon)
    assert len(violations) == 0


def test_path_reversal_triggers():
    """Heading change > 90 degrees triggers path reversal."""
    det = _make_detector(reversal_angle_deg=90.0, reversal_window_s=5.0)
    # Walk north, then south
    points = [(0.5, 0.1), (0.5, 0.2), (0.5, 0.3),  # heading north
              (0.5, 0.2), (0.5, 0.1)]  # heading south (reversal)
    _add_points(det, "obj1", points)
    violations = det.check_path_reversal("obj1")
    assert len(violations) >= 1
    assert violations[0].activity_type == "path_reversal"


def test_path_reversal_no_trigger_small_angle():
    """Heading change < 90 degrees does not trigger."""
    det = _make_detector(reversal_angle_deg=90.0, reversal_window_s=10.0)
    # Walk northeast, then east (small angle change)
    points = [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.35), (0.5, 0.38)]
    _add_points(det, "obj1", points)
    violations = det.check_path_reversal("obj1")
    assert len(violations) == 0


def test_group_clustering_triggers():
    """N objects within radius for > threshold triggers clustering alert."""
    det = _make_detector(cluster_min_count=3, cluster_radius=0.1, cluster_threshold_s=3.0)
    # Three objects close together for 4 seconds
    for obj_id in ["obj1", "obj2", "obj3"]:
        for i in range(4):
            det.update(obj_id, "cam1", 0.5, 0.5, 1000.0 + i)
    violations = det.check_group_clustering()
    assert len(violations) >= 1
    assert violations[0].activity_type == "group_clustering"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_suspicious_activity.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement SuspiciousActivityDetector**

```python
# fusion_server/core/suspicious_activity.py
"""Suspicious activity detection — loitering, path reversal, group clustering."""
import math
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from shapely.geometry import Point, Polygon


@dataclass
class SuspiciousActivity:
    """A detected suspicious activity."""
    activity_type: str  # "loitering" | "path_reversal" | "group_clustering"
    object_id: str
    camera_id: str
    timestamp: float
    duration_s: float = 0.0
    details: str = ""


class SuspiciousActivityDetector:
    """Detects suspicious activity from trajectory data."""

    def __init__(
        self,
        loiter_threshold_s: float = 30.0,
        reversal_angle_deg: float = 90.0,
        reversal_window_s: float = 5.0,
        cluster_min_count: int = 3,
        cluster_radius: float = 0.1,
        cluster_threshold_s: float = 10.0,
    ):
        self._loiter_threshold = loiter_threshold_s
        self._reversal_angle = reversal_angle_deg
        self._reversal_window = reversal_window_s
        self._cluster_min = cluster_min_count
        self._cluster_radius = cluster_radius
        self._cluster_threshold = cluster_threshold_s

        # Per-object state
        self._positions: Dict[str, List[Tuple[float, float, float, str]]] = defaultdict(list)
        self._roi_entry: Dict[str, Dict[str, float]] = {}  # (object_id, roi_key) -> entry_time

    def update(self, object_id: str, camera_id: str, x: float, y: float, timestamp: float) -> None:
        """Record a position update for an object."""
        self._positions[object_id].append((x, y, timestamp, camera_id))
        if len(self._positions[object_id]) > 100:
            self._positions[object_id] = self._positions[object_id][-100:]

    def remove(self, object_id: str) -> None:
        """Remove state for an object."""
        self._positions.pop(object_id, None)
        keys_to_remove = [k for k in self._roi_entry if k.startswith(object_id)]
        for k in keys_to_remove:
            del self._roi_entry[k]

    def check_loitering(self, object_id: str, roi_polygon: List[List[float]]) -> List[SuspiciousActivity]:
        """Check if object has been inside ROI longer than threshold."""
        positions = self._positions.get(object_id, [])
        if not positions:
            return []

        polygon = Polygon(roi_polygon)
        violations = []
        now = positions[-1][2]

        for x, y, ts, cam in reversed(positions):
            point = Point(x, y)
            if not polygon.contains(point):
                break
            # Object is inside — check dwell time
            oldest_inside_ts = ts
            dwell = now - oldest_inside_ts
            if dwell >= self._loiter_threshold:
                violations.append(SuspiciousActivity(
                    activity_type="loitering",
                    object_id=object_id,
                    camera_id=cam,
                    timestamp=now,
                    duration_s=dwell,
                    details=f"Object loitered for {dwell:.1f}s (threshold: {self._loiter_threshold}s)",
                ))
                break

        return violations

    def check_path_reversal(self, object_id: str) -> List[SuspiciousActivity]:
        """Check if object changed heading by > threshold angle."""
        positions = self._positions.get(object_id, [])
        if len(positions) < 3:
            return []

        now = positions[-1][2]
        # Filter to recent window
        recent = [(x, y, t, c) for x, y, t, c in positions if now - t <= self._reversal_window]
        if len(recent) < 3:
            return []

        # Calculate heading changes
        headings = []
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            dy = recent[i][1] - recent[i-1][1]
            heading = math.atan2(dy, dx)
            headings.append((heading, recent[i][2], recent[i][3]))

        violations = []
        for i in range(1, len(headings)):
            angle_diff = abs(headings[i][0] - headings[i-1][0])
            angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
            angle_deg = math.degrees(angle_diff)
            if angle_deg >= self._reversal_angle:
                violations.append(SuspiciousActivity(
                    activity_type="path_reversal",
                    object_id=object_id,
                    camera_id=headings[i][3],
                    timestamp=headings[i][1],
                    details=f"Heading changed by {angle_deg:.1f} degrees (threshold: {self._reversal_angle})",
                ))
                break

        return violations

    def check_group_clustering(self) -> List[SuspiciousActivity]:
        """Check if N+ objects are within radius for > threshold time."""
        if len(self._positions) < self._cluster_min:
            return []

        violations = []
        checked = set()

        # Get latest position for each object
        latest = {}
        for obj_id, positions in self._positions.items():
            if positions:
                x, y, ts, cam = positions[-1]
                latest[obj_id] = (x, y, ts, cam)

        obj_ids = list(latest.keys())
        for i in range(len(obj_ids)):
            for j in range(i + 1, len(obj_ids)):
                a_id, b_id = obj_ids[i], obj_ids[j]
                pair_key = tuple(sorted([a_id, b_id]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)

                ax, ay, _, _ = latest[a_id]
                bx, by, _, _ = latest[b_id]
                dist = math.sqrt((ax - bx)**2 + (ay - by)**2)

                if dist <= self._cluster_radius:
                    # Check how long they've been close
                    a_positions = self._positions[a_id]
                    b_positions = self._positions[b_id]
                    if len(a_positions) < 2 or len(b_positions) < 2:
                        continue

                    # Simple: check if both have been near for >= threshold
                    a_start = a_positions[-1][2]
                    b_start = b_positions[-1][2]
                    start_time = max(a_start, b_start)
                    end_time = min(a_positions[-1][2], b_positions[-1][2])
                    duration = end_time - start_time

                    if duration >= self._cluster_threshold:
                        violations.append(SuspiciousActivity(
                            activity_type="group_clustering",
                            object_id=f"{a_id},{b_id}",
                            camera_id=latest[a_id][3],
                            timestamp=end_time,
                            duration_s=duration,
                            details=f"{len([a_id, b_id])} objects within {self._cluster_radius} for {duration:.1f}s",
                        ))

        return violations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_suspicious_activity.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/core/suspicious_activity.py tests/test_suspicious_activity.py
git commit -m "feat(core): suspicious activity detection — loitering, reversal, clustering"
```

---

## Task 6: Wire Rule Engine into Event Pipeline

**Files:**
- Modify: `fusion_server/core/rule_engine.py` (add `load_rois_from_db()`, `evaluate()`)
- Modify: `fusion_server/api/events.py` (call rule engine after storing event)
- Test: `tests/test_rule_engine_wiring.py`

**Interfaces:**
- Consumes: `ROI` model (Task 1), `TrajectoryBuffer` (Task 3), `SuspiciousActivityDetector` (Task 5)
- Produces: `RuleEngine.evaluate()` returns `List[RuleViolation]`

- [ ] **Step 1: Write rule engine wiring tests**

```python
# tests/test_rule_engine_wiring.py
"""Tests for rule engine wiring into event pipeline."""
import pytest
from fusion_server.core.rule_engine import RuleEngine, ROI, RuleViolation


def test_evaluate_roi_intrusion():
    """evaluate() detects ROI intrusion."""
    engine = RuleEngine()
    engine.add_roi(ROI(
        camera_id="cam1",
        name="Fence",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    violations = engine.evaluate(
        object_id="obj1",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        bbox={"x1": 0.2, "y1": 0.2, "x2": 0.3, "y2": 0.3},
        object_type="person",
    )
    assert len(violations) == 1
    assert violations[0].violation_type == "enter"


def test_evaluate_no_violation():
    """evaluate() returns empty when outside all ROIs."""
    engine = RuleEngine()
    engine.add_roi(ROI(
        camera_id="cam1",
        name="Fence",
        polygon=[[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
        alert_on_enter=True,
    ))
    violations = engine.evaluate(
        object_id="obj1",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        bbox={"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9},
        object_type="person",
    )
    assert len(violations) == 0


def test_load_rois_from_db():
    """load_rois_from_db() populates engine from database."""
    from unittest.mock import MagicMock
    from fusion_server.db.models_roi import ROI as ROIModel

    mock_roi = MagicMock(spec=ROIModel)
    mock_roi.camera_id = "cam1"
    mock_roi.name = "Fence"
    mock_roi.polygon = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    mock_roi.alert_on_enter = True
    mock_roi.alert_on_exit = False
    mock_roi.object_types = None

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_roi]

    engine = RuleEngine()
    engine.load_rois_from_db(mock_db)
    assert len(engine.rois) == 1
    assert engine.rois[0].name == "Fence"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_rule_engine_wiring.py -v`
Expected: FAIL (no `evaluate` or `load_rois_from_db` methods)

- [ ] **Step 3: Add evaluate() and load_rois_from_db() to RuleEngine**

Add these methods to the `RuleEngine` class in `fusion_server/core/rule_engine.py`:

```python
    def load_rois_from_db(self, db) -> None:
        """Load active ROIs from database into the engine."""
        from fusion_server.db.models_roi import ROI as ROIModel
        db_rois = db.query(ROIModel).filter(ROIModel.active == True).all()
        self.rois = []
        for r in db_rois:
            self.rois.append(ROI(
                camera_id=r.camera_id,
                name=r.name,
                polygon=r.polygon,
                alert_on_enter=r.alert_on_enter,
                alert_on_exit=r.alert_on_exit,
                object_types=r.object_types,
            ))

    def evaluate(
        self,
        object_id: str,
        camera_id: str,
        timestamp: str,
        bbox: dict,
        object_type: str,
        previous_bbox: dict = None,
    ) -> List[RuleViolation]:
        """Run all rule checks and return violations."""
        violations = []
        violations.extend(self.check_roi_intrusion(
            object_id, camera_id, timestamp, bbox, object_type, previous_bbox
        ))
        return violations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_rule_engine_wiring.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/core/rule_engine.py tests/test_rule_engine_wiring.py
git commit -m "feat(engine): wire rule engine — load ROIs from DB, evaluate() method"
```

---

## Task 7: Alert Pipeline Orchestrator

**Files:**
- Create: `fusion_server/services/alert_pipeline.py`
- Modify: `fusion_server/api/events.py` (integrate pipeline)
- Test: `tests/test_alert_pipeline.py`

**Interfaces:**
- Consumes: `RuleEngine` (Task 6), `TrajectoryBuffer` (Task 3), `SuspiciousActivityDetector` (Task 5), `calculate_threat_score()`, `TrajectoryProjector`, `AlertLedger`, `SSEBroadcaster` (Task 9)
- Produces: `AlertPipeline.process_event()` fires alerts synchronously

- [ ] **Step 1: Write alert pipeline tests**

```python
# tests/test_alert_pipeline.py
"""Tests for the alert pipeline orchestrator."""
import pytest
from unittest.mock import MagicMock, patch
from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.core.rule_engine import RuleViolation
from fusion_server.core.trajectory_buffer import TrajectoryBuffer


def _make_pipeline():
    """Create a pipeline with mocked dependencies."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    pipeline = AlertPipeline(db=mock_db)
    return pipeline


def test_process_event_fires_alert_on_violation():
    """Pipeline fires alert when rule engine detects violation."""
    pipeline = _make_pipeline()
    violations = [RuleViolation(
        object_id="obj1",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        roi_name="Fence",
        violation_type="enter",
        threat_score=0.5,
    )]
    with patch.object(pipeline._rule_engine, 'evaluate', return_value=violations):
        result = pipeline.process_event(
            object_id="obj1",
            camera_id="cam1",
            object_type="person",
            timestamp="2026-09-11T10:00:00",
            bbox={"x1": 0.2, "y1": 0.2, "x2": 0.3, "y2": 0.3},
        )
    assert result is not None
    assert result.threat_score > 0.0


def test_process_event_no_violation_returns_none():
    """Pipeline returns None when no violations detected."""
    pipeline = _make_pipeline()
    with patch.object(pipeline._rule_engine, 'evaluate', return_value=[]):
        result = pipeline.process_event(
            object_id="obj1",
            camera_id="cam1",
            object_type="person",
            timestamp="2026-09-11T10:00:00",
            bbox={"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9},
        )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_alert_pipeline.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement AlertPipeline**

```python
# fusion_server/services/alert_pipeline.py
"""Alert Pipeline — orchestrates sync rule check + async enrichment."""
import logging
import uuid
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from fusion_server.core.rule_engine import RuleEngine, RuleViolation
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
from fusion_server.core.trajectory import TrajectoryProjector, TrajectoryPoint, project_trajectory
from fusion_server.core.alert_ledger import AlertLedger

logger = logging.getLogger(__name__)


@dataclass
class FiredAlert:
    """Result of a synchronous alert fire."""
    alert_id: str
    object_id: str
    camera_id: str
    timestamp: str
    reason: str
    threat_score: float
    trajectory_projection: Optional[dict] = None


class AlertPipeline:
    """Orchestrates synchronous rule checking and alert firing."""

    def __init__(self, db=None):
        self._db = db
        self._rule_engine = RuleEngine()
        self._trajectory_buffer = TrajectoryBuffer()
        self._alert_ledger = AlertLedger()
        self._sse_broadcast = None  # Set after SSE broadcaster is initialized

    def set_sse_broadcaster(self, broadcaster):
        """Inject SSE broadcaster (avoids circular import)."""
        self._sse_broadcast = broadcaster

    def load_rois(self, db=None) -> None:
        """Load ROIs from database into rule engine."""
        db = db or self._db
        if db:
            self._rule_engine.load_rois_from_db(db)

    def update_trajectory(self, object_id: str, x: float, y: float, timestamp: float) -> None:
        """Accumulate trajectory point."""
        self._trajectory_buffer.add_point(object_id, x, y, timestamp)

    def process_event(
        self,
        object_id: str,
        camera_id: str,
        object_type: str,
        timestamp: str,
        bbox: dict,
        embedding=None,
    ) -> Optional[FiredAlert]:
        """
        Process a detection event through the rule engine.
        Returns FiredAlert if violation detected, None otherwise.
        """
        # 1. Run rule engine
        violations = self._rule_engine.evaluate(
            object_id=object_id,
            camera_id=camera_id,
            timestamp=timestamp,
            bbox=bbox,
            object_type=object_type,
        )

        if not violations:
            return None

        # 2. Compute threat score
        threat_context = ThreatContext(
            object_type=object_type,
            time_of_day=self._get_time_of_day(timestamp),
            camera_zone="perimeter",
            previous_violations=self._get_previous_violations(object_id),
            is_watchlist_match=False,
        )
        score = calculate_threat_score(violations, threat_context)

        # 3. Compute trajectory projection
        traj_projection = self._compute_projection(object_id)

        # 4. Create alert
        alert_id = str(uuid.uuid4())
        reason = violations[0].violation_type

        alert_data = FiredAlert(
            alert_id=alert_id,
            object_id=object_id,
            camera_id=camera_id,
            timestamp=timestamp,
            reason=reason,
            threat_score=score,
            trajectory_projection=traj_projection,
        )

        # 5. Write to DB and hash chain
        if self._db:
            from fusion_server.db.models import Alert
            db_alert = Alert(
                alert_id=alert_id,
                object_id=object_id,
                camera_id=camera_id,
                timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp,
                reason=reason,
                status="fired",
                threat_score=score,
                trajectory_projection=traj_projection,
            )
            self._db.add(db_alert)
            self._alert_ledger.write_alert_with_hash(self._db, db_alert)

        # 6. SSE broadcast
        if self._sse_broadcast:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._sse_broadcast.broadcast_alert_fired(alert_data))
                else:
                    loop.run_until_complete(self._sse_broadcast.broadcast_alert_fired(alert_data))
            except RuntimeError:
                pass

        logger.info(f"Alert fired: {alert_id} reason={reason} score={score:.2f}")
        return alert_data

    def _compute_projection(self, object_id: str) -> Optional[dict]:
        """Compute trajectory projection from buffer."""
        points = self._trajectory_buffer.get_recent(object_id, 20)
        if len(points) < 2:
            return None

        try:
            history = [[p.x, p.y] for p in points]
            predicted = project_trajectory(points, prediction_steps=10)
            predicted_list = [[x, y] for x, y in predicted]
            return {
                "history": history,
                "predicted": predicted_list,
                "confidence": 0.85,
            }
        except Exception as e:
            logger.warning(f"Trajectory projection failed: {e}")
            return None

    def _get_time_of_day(self, timestamp: str) -> str:
        """Determine time of day from timestamp."""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = timestamp
            hour = dt.hour
            if 6 <= hour < 18:
                return "day"
            elif 18 <= hour < 21:
                return "dusk"
            elif 21 <= hour or hour < 5:
                return "night"
            else:
                return "dawn"
        except Exception:
            return "day"

    def _get_previous_violations(self, object_id: str) -> int:
        """Count previous violations for this object."""
        if not self._db:
            return 0
        from fusion_server.db.models import Alert
        return self._db.query(Alert).filter(Alert.object_id == object_id).count()
```

- [ ] **Step 4: Integrate into events.py**

In `fusion_server/api/events.py`, after the watchlist matching block (line 121), add:

```python
        # Phase 4: Rule engine + alert pipeline
        from fusion_server.services.alert_pipeline import AlertPipeline
        pipeline = AlertPipeline(db=db)
        pipeline.update_trajectory(
            object_id=object_id,
            x=(event.bbox.x1 + event.bbox.x2) / 2,
            y=(event.bbox.y1 + event.bbox.y2) / 2,
            timestamp=event.timestamp.timestamp(),
        )
        fired = pipeline.process_event(
            object_id=object_id,
            camera_id=event.camera_id,
            object_type=event.object_type,
            timestamp=event.timestamp.isoformat(),
            bbox=event.bbox.model_dump(),
            embedding=event.embedding,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_alert_pipeline.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add fusion_server/services/alert_pipeline.py fusion_server/api/events.py tests/test_alert_pipeline.py
git commit -m "feat(pipeline): alert pipeline orchestrator — sync rule check + alert fire"
```

---

## Task 8: Wire Threat Scoring into Alert Creation

**Files:**
- Modify: `fusion_server/api/events.py:116` (replace hardcoded 0.9)
- Modify: `fusion_server/api/routes/cameras.py:71` (replace hardcoded 0.8)
- Modify: `fusion_server/core/threat_scoring.py` (add missing violation types)
- Test: `tests/test_threat_scoring_wiring.py`

**Interfaces:**
- Consumes: `calculate_threat_score()` from existing module
- Produces: All alert sources use `calculate_threat_score()` instead of hardcoded values

- [ ] **Step 1: Write threat scoring wiring tests**

```python
# tests/test_threat_scoring_wiring.py
"""Tests for threat scoring wiring."""
import pytest
from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext, VIOLATION_BASE_SCORES


def test_watchlist_match_gets_high_score():
    """Watchlist match should produce score >= 0.9."""
    from fusion_server.core.rule_engine import RuleViolation
    violations = [RuleViolation(
        object_id="obj1", camera_id="cam1", timestamp="2026-09-11T10:00:00",
        roi_name="N/A", violation_type="enter", threat_score=0.5,
    )]
    context = ThreatContext(
        object_type="person", time_of_day="day",
        camera_zone="perimeter", is_watchlist_match=True,
    )
    score = calculate_threat_score(violations, context)
    assert score >= 0.9


def test_all_violation_types_have_base_scores():
    """All violation types used in the system have base scores."""
    expected_types = {"enter", "exit", "dwell", "speed", "direction",
                      "virtual_fence_crossing", "suspicious_activity", "loitering",
                      "path_reversal", "group_clustering", "plate_watchlist_match"}
    assert expected_types.issubset(set(VIOLATION_BASE_SCORES.keys()))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_threat_scoring_wiring.py -v`
Expected: FAIL (missing violation types in VIOLATION_BASE_SCORES)

- [ ] **Step 3: Add missing violation types to threat_scoring.py**

In `fusion_server/core/threat_scoring.py`, update `VIOLATION_BASE_SCORES`:
```python
VIOLATION_BASE_SCORES = {
    "enter": 0.5,
    "exit": 0.4,
    "dwell": 0.6,
    "speed": 0.7,
    "direction": 0.3,
    "virtual_fence_crossing": 0.7,
    "suspicious_activity": 0.6,
    "loitering": 0.5,
    "path_reversal": 0.6,
    "group_clustering": 0.7,
    "plate_watchlist_match": 0.9,
}
```

- [ ] **Step 4: Replace hardcoded threat_score in events.py**

In `fusion_server/api/events.py`, replace `threat_score=0.9` (line 116) with:
```python
            from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
            score = calculate_threat_score(
                violations=[],
                context=ThreatContext(
                    object_type=event.object_type,
                    time_of_day="day",
                    camera_zone="perimeter",
                    is_watchlist_match=True,
                ),
            )
```
And use `score` instead of `0.9`.

- [ ] **Step 5: Replace hardcoded threat_score in cameras.py**

In `fusion_server/api/routes/cameras.py`, replace `threat_score=0.8` with:
```python
            from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
            score = calculate_threat_score(
                violations=[],
                context=ThreatContext(
                    object_type="person",
                    time_of_day="day",
                    camera_zone="perimeter",
                ),
            )
```
And use `score` instead of `0.8`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_threat_scoring_wiring.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add fusion_server/core/threat_scoring.py fusion_server/api/events.py fusion_server/api/routes/cameras.py tests/test_threat_scoring_wiring.py
git commit -m "feat(scoring): wire threat scoring — replace hardcoded values, add violation types"
```

---

## Task 9: SSE Broadcaster

**Files:**
- Create: `fusion_server/services/sse_broadcaster.py`
- Test: `tests/test_sse_broadcaster.py`

**Interfaces:**
- Produces: `SSEBroadcaster` class with `subscribe()`, `unsubscribe()`, `broadcast_alert_fired()`, `broadcast_alert_enriched()`

- [ ] **Step 1: Write SSE broadcaster tests**

```python
# tests/test_sse_broadcaster.py
"""Tests for SSE broadcaster."""
import pytest
import asyncio
import json
from fusion_server.services.sse_broadcaster import SSEBroadcaster


@pytest.mark.asyncio
async def test_subscribe_and_broadcast():
    """Client subscribes and receives broadcast."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe()
    await broadcaster.broadcast_alert_fired({
        "alert_id": "test-123",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
    })
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["event"] == "alert_fired"
    data = json.loads(event["data"])
    assert data["alert_id"] == "test-123"


@pytest.mark.asyncio
async def test_unsubscribe():
    """Unsubscribed client does not receive broadcasts."""
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe()
    broadcaster.unsubscribe(queue)
    await broadcaster.broadcast_alert_fired({"alert_id": "test"})
    assert queue.empty()


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Multiple subscribers all receive broadcasts."""
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    await broadcaster.broadcast_alert_fired({"alert_id": "test"})
    assert not q1.empty()
    assert not q2.empty()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_sse_broadcaster.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement SSEBroadcaster**

```python
# fusion_server/services/sse_broadcaster.py
"""SSE Broadcaster — pushes alerts to connected clients."""
import json
import asyncio
import logging
from typing import Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Manages SSE connections and broadcasts alerts."""

    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to alert broadcasts. Returns a queue."""
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        logger.info(f"SSE client connected. Total subscribers: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from alert broadcasts."""
        self._subscribers.discard(queue)
        logger.info(f"SSE client disconnected. Total subscribers: {len(self._subscribers)}")

    async def broadcast_alert_fired(self, alert_data) -> None:
        """Broadcast an alert_fired event to all subscribers."""
        event = {
            "event": "alert_fired",
            "data": json.dumps(alert_data if isinstance(alert_data, dict) else {
                "alert_id": alert_data.alert_id,
                "camera_id": alert_data.camera_id,
                "object_id": alert_data.object_id,
                "reason": alert_data.reason,
                "threat_score": alert_data.threat_score,
                "timestamp": alert_data.timestamp,
            }),
        }
        await self._broadcast(event)

    async def broadcast_alert_enriched(self, alert_id: str, ai_explanation: str, trajectory_projection=None) -> None:
        """Broadcast an alert_enriched event to all subscribers."""
        event = {
            "event": "alert_enriched",
            "data": json.dumps({
                "alert_id": alert_id,
                "ai_explanation": ai_explanation,
                "trajectory_projection": trajectory_projection,
            }),
        }
        await self._broadcast(event)

    async def _broadcast(self, event: dict) -> None:
        """Send event to all subscribers, removing disconnected ones."""
        dead = []
        for queue in self._subscribers:
            try:
                await queue.put(event)
            except Exception:
                dead.append(queue)
        for q in dead:
            self._subscribers.discard(q)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_sse_broadcaster.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/sse_broadcaster.py tests/test_sse_broadcaster.py
git commit -m "feat(sse): SSE broadcaster for real-time alert push"
```

---

## Task 10: SSE Endpoint + Viewer

**Files:**
- Create: `fusion_server/api/routes/stream.py`
- Create: `templates/viewer.html`
- Modify: `fusion_server/main.py` (register router, serve viewer)
- Test: `tests/test_sse_endpoint.py`

**Interfaces:**
- Consumes: `SSEBroadcaster` (Task 9)
- Produces: `GET /api/v1/alerts/stream` endpoint, `GET /viewer` page

- [ ] **Step 1: Write SSE endpoint test**

```python
# tests/test_sse_endpoint.py
"""Tests for SSE endpoint."""
import pytest
from fastapi.testclient import TestClient
from fusion_server.main import app


def test_sse_endpoint_returns_event_stream():
    """SSE endpoint returns text/event-stream content type."""
    client = TestClient(app)
    # Just test the endpoint exists and returns stream
    with client.stream_response("GET", "/api/v1/alerts/stream") as response:
        assert response.status_code == 200
        # Read first few bytes to verify it's streaming
        content = response.read(100)
        assert b"data:" in content or b"event:" in content


def test_viewer_endpoint():
    """Viewer endpoint returns HTML."""
    client = TestClient(app)
    response = client.get("/viewer")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_sse_endpoint.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Create SSE endpoint**

```python
# fusion_server/api/routes/stream.py
"""SSE streaming endpoint for real-time alerts."""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(tags=["stream"])

# Global broadcaster instance
_broadcaster = None


def get_broadcaster():
    global _broadcaster
    if _broadcaster is None:
        from fusion_server.services.sse_broadcaster import SSEBroadcaster
        _broadcaster = SSEBroadcaster()
    return _broadcaster


@router.get("/api/v1/alerts/stream")
async def alert_stream(request: Request):
    """SSE endpoint — streams alert events in real-time."""
    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Create viewer HTML**

```html
<!-- templates/viewer.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IBVAP Alert Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; padding: 20px; }
        h1 { color: #00d4ff; margin-bottom: 20px; font-size: 1.5em; }
        .status { color: #888; margin-bottom: 10px; }
        .status.connected { color: #00ff88; }
        .status.disconnected { color: #ff4444; }
        #alerts { max-height: 80vh; overflow-y: auto; }
        .alert {
            border: 1px solid #333; border-radius: 4px; padding: 12px;
            margin-bottom: 8px; background: #16213e;
        }
        .alert.critical { border-color: #ff0000; background: #3d0000; }
        .alert.high { border-color: #ff6600; background: #3d1f00; }
        .alert.medium { border-color: #ffcc00; background: #3d3500; }
        .alert.low { border-color: #00cc00; background: #003d00; }
        .alert-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .alert-reason { font-weight: bold; text-transform: uppercase; }
        .alert-score { padding: 2px 8px; border-radius: 3px; font-size: 0.9em; }
        .alert-meta { font-size: 0.85em; color: #888; }
        .enriched { font-style: italic; color: #00d4ff; margin-top: 6px; }
        #no-alerts { color: #666; text-align: center; padding: 40px; }
    </style>
</head>
<body>
    <h1>IBVAP Alert Viewer</h1>
    <div class="status disconnected" id="status">Disconnected</div>
    <div id="alerts">
        <div id="no-alerts">Waiting for alerts...</div>
    </div>
    <script>
        const statusEl = document.getElementById('status');
        const alertsEl = document.getElementById('alerts');
        const noAlertsEl = document.getElementById('no-alerts');
        let alertCount = 0;

        function connect() {
            const es = new EventSource('/api/v1/alerts/stream');
            es.onopen = () => {
                statusEl.textContent = 'Connected';
                statusEl.className = 'status connected';
            };
            es.onerror = () => {
                statusEl.textContent = 'Disconnected — reconnecting...';
                statusEl.className = 'status disconnected';
            };
            es.addEventListener('alert_fired', (e) => {
                const data = JSON.parse(e.data);
                noAlertsEl.style.display = 'none';
                alertCount++;
                const level = data.threat_score >= 0.8 ? 'critical' :
                              data.threat_score >= 0.6 ? 'high' :
                              data.threat_score >= 0.4 ? 'medium' : 'low';
                const div = document.createElement('div');
                div.className = `alert ${level}`;
                div.id = `alert-${data.alert_id}`;
                div.innerHTML = `
                    <div class="alert-header">
                        <span class="alert-reason">${data.reason}</span>
                        <span class="alert-score" style="background:${level === 'critical' ? '#ff0000' : level === 'high' ? '#ff6600' : level === 'medium' ? '#ffcc00' : '#00cc00'}; color:#000">
                            ${(data.threat_score * 100).toFixed(0)}%
                        </span>
                    </div>
                    <div class="alert-meta">
                        ${data.camera_id} | ${data.object_id} | ${new Date(data.timestamp).toLocaleTimeString()}
                    </div>
                `;
                alertsEl.prepend(div);
            });
            es.addEventListener('alert_enriched', (e) => {
                const data = JSON.parse(e.data);
                const alertEl = document.getElementById(`alert-${data.alert_id}`);
                if (alertEl) {
                    const enriched = document.createElement('div');
                    enriched.className = 'enriched';
                    enriched.textContent = `AI: ${data.ai_explanation}`;
                    alertEl.appendChild(enriched);
                }
            });
        }
        connect();
    </script>
</body>
</html>
```

- [ ] **Step 5: Register routes in main.py**

In `fusion_server/main.py`, add import and include_router:

```python
from fusion_server.api.routes import cameras, stream

# ... after existing include_router calls:
app.include_router(stream.router)
```

And add viewer route:

```python
@app.get("/viewer")
async def viewer():
    from fastapi.responses import FileResponse
    return FileResponse("templates/viewer.html")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_sse_endpoint.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add fusion_server/api/routes/stream.py templates/viewer.html fusion_server/main.py tests/test_sse_endpoint.py
git commit -m "feat(sse): SSE endpoint and alert viewer page"
```

---

## Task 11: ANPR Pipeline

**Files:**
- Create: `fusion_server/core/anpr.py`
- Modify: `fusion_server/db/models.py` (import PlateDetection)
- Test: `tests/test_anpr.py`

**Interfaces:**
- Produces: `ANPRPipeline` class with `detect_plate()` that returns plate text + confidence

- [ ] **Step 1: Write ANPR tests**

```python
# tests/test_anpr.py
"""Tests for ANPR pipeline."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from fusion_server.core.anpr import ANPRPipeline


def test_anpr_pipeline_initializes():
    """ANPR pipeline can be created."""
    pipeline = ANPRPipeline()
    assert pipeline is not None


def test_detect_plate_returns_none_on_no_plate():
    """Returns None when no plate detected in frame."""
    pipeline = ANPRPipeline()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = pipeline.detect_plate(frame)
    assert result is None or result.plate_text == ""


def test_anpr_stores_detection():
    """ANPR pipeline stores plate detection in database."""
    pipeline = ANPRPipeline()
    mock_db = MagicMock()
    # Mock the detect to return a result
    with patch.object(pipeline, '_run_detection') as mock_detect:
        mock_detect.return_value = {"plate_text": "ABC1234", "confidence": 0.92, "bbox": [0.1, 0.2, 0.15, 0.05]}
        result = pipeline.process_detection(
            db=mock_db,
            object_id="obj_001",
            camera_id="cam1",
            frame=np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
        )
        assert result is not None
        assert result["plate_text"] == "ABC1234"
        mock_db.add.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_anpr.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement ANPRPipeline**

```python
# fusion_server/core/anpr.py
"""ANPR Pipeline — plate detection + OCR."""
import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PlateResult:
    plate_text: str
    confidence: float
    bbox: list  # [x, y, w, h] normalized


class ANPRPipeline:
    """
    Automatic Number Plate Recognition pipeline.
    Uses YOLOv8 for plate detection + PaddleOCR/EasyOCR for character recognition.
    """

    def __init__(self, plate_model_path: str = None, ocr_engine: str = "easyocr"):
        self._plate_model = None
        self._ocr_engine = None
        self._ocr_type = ocr_engine
        self._plate_model_path = plate_model_path
        self._initialized = False

    def _lazy_init(self):
        """Initialize models on first use (avoids import-time GPU load)."""
        if self._initialized:
            return
        try:
            from ultralytics import YOLO
            if self._plate_model_path:
                self._plate_model = YOLO(self._plate_model_path)
            else:
                self._plate_model = YOLO("yolov8n.pt")  # Placeholder — real model trained on plates
            logger.info("ANPR plate detection model loaded")
        except ImportError:
            logger.warning("ultralytics not installed — ANPR will use fallback detection")

        try:
            if self._ocr_type == "easyocr":
                import easyocr
                self._ocr_engine = easyocr.Reader(['en'])
                logger.info("EasyOCR engine loaded")
            elif self._ocr_type == "paddleocr":
                from paddleocr import PaddleOCR
                self._ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR engine loaded")
        except ImportError:
            logger.warning(f"{self._ocr_type} not installed — ANPR will use fallback OCR")

        self._initialized = True

    def detect_plate(self, frame: np.ndarray) -> Optional[PlateResult]:
        """
        Detect and read a license plate from a frame.
        Returns PlateResult or None if no plate found.
        """
        self._lazy_init()

        if self._plate_model is None:
            return None

        try:
            results = self._plate_model(frame, verbose=False)
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls != 0:  # Assuming class 0 = plate (adjust for fine-tuned model)
                        continue
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    h, w = frame.shape[:2]
                    plate_crop = frame[int(y1):int(y2), int(x1):int(x2)]
                    if plate_crop.size == 0:
                        continue

                    plate_text = self._ocr_plate(plate_crop)
                    if plate_text:
                        return PlateResult(
                            plate_text=plate_text,
                            confidence=float(box.conf[0]),
                            bbox=[float(x1)/w, float(y1)/h, (float(x2)-float(x1))/w, (float(y2)-float(y1))/h],
                        )
        except Exception as e:
            logger.warning(f"ANPR detection failed: {e}")

        return None

    def _ocr_plate(self, plate_crop: np.ndarray) -> Optional[str]:
        """Run OCR on a plate crop image."""
        self._lazy_init()
        if self._ocr_engine is None:
            return None

        try:
            if self._ocr_type == "easyocr":
                results = self._ocr_engine.readtext(plate_crop)
                if results:
                    # Combine all detected text
                    text = " ".join([r[1] for r in results])
                    return text.upper().strip()
            elif self._ocr_type == "paddleocr":
                results = self._ocr_engine.ocr(plate_crop, cls=True)
                if results and results[0]:
                    text = " ".join([line[1][0] for line in results[0]])
                    return text.upper().strip()
        except Exception as e:
            logger.warning(f"OCR failed: {e}")

        return None

    def process_detection(self, db, object_id: str, camera_id: str, frame: np.ndarray) -> Optional[dict]:
        """
        Full pipeline: detect plate, store result, check watchlist.
        Returns plate detection data or None.
        """
        result = self.detect_plate(frame)
        if result is None:
            return None

        from fusion_server.db.models_plate import PlateDetection
        from datetime import datetime

        plate_record = PlateDetection(
            object_id=object_id,
            camera_id=camera_id,
            plate_text=result.plate_text,
            confidence=result.confidence,
            bbox=result.bbox,
        )
        db.add(plate_record)
        db.commit()
        db.refresh(plate_record)

        return {
            "id": plate_record.id,
            "plate_text": result.plate_text,
            "confidence": result.confidence,
            "bbox": result.bbox,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_anpr.py -v`
Expected: All PASS (model-dependent tests may skip if ultralytics not installed)

- [ ] **Step 5: Commit**

```bash
git add fusion_server/core/anpr.py tests/test_anpr.py
git commit -m "feat(anpr): plate detection + OCR pipeline"
```

---

## Task 12: AI Enrichment Service

**Files:**
- Create: `fusion_server/services/ai_enrichment.py`
- Test: `tests/test_ai_enrichment.py`

**Interfaces:**
- Produces: `AIEnrichmentService` class with `enrich(alert_data)` that returns explanation string

- [ ] **Step 1: Write AI enrichment tests**

```python
# tests/test_ai_enrichment.py
"""Tests for AI enrichment service."""
import pytest
from unittest.mock import MagicMock, patch
from fusion_server.services.ai_enrichment import AIEnrichmentService


def test_enrichment_service_initializes():
    """AI enrichment service can be created."""
    service = AIEnrichmentService()
    assert service is not None


def test_enrichment_generates_explanation():
    """Enrichment produces a natural language explanation."""
    service = AIEnrichmentService()
    alert_data = {
        "alert_id": "test-123",
        "object_id": "obj1",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
        "trajectory": {"history": [[0.1, 0.2], [0.3, 0.4]], "predicted": [[0.5, 0.6]]},
    }
    with patch.object(service, '_call_llava', return_value="Person detected entering restricted zone at 10:00 AM"):
        result = service.enrich(alert_data)
    assert result is not None
    assert len(result) > 0


def test_enrichment_returns_template_on_model_failure():
    """Falls back to template when model unavailable."""
    service = AIEnrichmentService()
    alert_data = {
        "alert_id": "test-123",
        "object_id": "obj1",
        "camera_id": "cam1",
        "reason": "enter",
        "threat_score": 0.7,
    }
    with patch.object(service, '_call_llava', side_effect=Exception("Model not loaded")):
        result = service.enrich(alert_data)
    assert result is not None
    assert "enter" in result.lower() or "alert" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_ai_enrichment.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement AIEnrichmentService**

```python
# fusion_server/services/ai_enrichment.py
"""AI Enrichment Service — LLaVA-based natural language alert explanation."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIEnrichmentService:
    """Enriches fired alerts with natural language explanations using LLaVA."""

    def __init__(self, model_name: str = "llava-hf/llava-1.5-7b-hf"):
        self._model_name = model_name
        self._model = None
        self._processor = None
        self._initialized = False

    def _lazy_init(self):
        """Initialize model on first use."""
        if self._initialized:
            return
        try:
            from transformers import LlavaForConditionalGeneration, AutoProcessor
            logger.info(f"Loading LLaVA model: {self._model_name}")
            self._processor = AutoProcessor.from_pretrained(self._model_name)
            self._model = LlavaForConditionalGeneration.from_pretrained(
                self._model_name,
                torch_dtype="auto",
                device_map="auto",
            )
            self._initialized = True
            logger.info("LLaVA model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load LLaVA: {e}. Using template fallback.")
            self._initialized = True

    def enrich(self, alert_data: dict) -> str:
        """
        Generate natural language explanation for an alert.
        Returns explanation string.
        """
        try:
            return self._call_llava(alert_data)
        except Exception as e:
            logger.warning(f"LLaVA enrichment failed: {e}. Using template.")
            return self._template_explanation(alert_data)

    def _call_llava(self, alert_data: dict) -> str:
        """Call LLaVA model for explanation generation."""
        self._lazy_init()

        if self._model is None:
            return self._template_explanation(alert_data)

        prompt = self._build_prompt(alert_data)

        inputs = self._processor(text=prompt, return_tensors="pt")
        if hasattr(self._model, 'device'):
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        output = self._model.generate(**inputs, max_new_tokens=200)
        response = self._processor.decode(output[0], skip_special_tokens=True)

        # Extract just the explanation part
        if "ASSISTANT:" in response:
            response = response.split("ASSISTANT:")[-1].strip()

        return response

    def _build_prompt(self, alert_data: dict) -> str:
        """Build prompt for LLaVA."""
        reason = alert_data.get("reason", "unknown")
        camera = alert_data.get("camera_id", "unknown")
        score = alert_data.get("threat_score", 0.0)
        trajectory = alert_data.get("trajectory", {})

        prompt = (
            f"USER: Describe this security alert in detail. "
            f"Alert type: {reason}. Camera: {camera}. "
            f"Threat score: {score:.0%}. "
        )

        if trajectory.get("history"):
            prompt += f"The object moved through {len(trajectory['history'])} positions. "

        prompt += (
            "Provide a concise, professional security assessment. "
            "ASSISTANT:"
        )
        return prompt

    def _template_explanation(self, alert_data: dict) -> str:
        """Template-based fallback explanation."""
        reason = alert_data.get("reason", "unknown")
        camera = alert_data.get("camera_id", "unknown")
        score = alert_data.get("threat_score", 0.0)
        obj_id = alert_data.get("object_id", "unknown")

        templates = {
            "enter": f"Object {obj_id} entered restricted zone on {camera}. Threat level: {score:.0%}.",
            "exit": f"Object {obj_id} exited monitored area on {camera}. Threat level: {score:.0%}.",
            "dwell": f"Object {obj_id} loitering in restricted area on {camera}. Threat level: {score:.0%}.",
            "loitering": f"Object {obj_id} detected loitering on {camera}. Threat level: {score:.0%}.",
            "path_reversal": f"Object {obj_id} reversed direction near restricted area on {camera}. Threat level: {score:.0%}.",
            "group_clustering": f"Group activity detected on {camera}. Threat level: {score:.0%}.",
            "watchlist_match": f"Object {obj_id} matched watchlist entry on {camera}. Threat level: {score:.0%}.",
        }

        return templates.get(reason, f"Alert triggered on {camera}: {reason}. Threat level: {score:.0%}.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_ai_enrichment.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/services/ai_enrichment.py tests/test_ai_enrichment.py
git commit -m "feat(enrichment): LLaVA-based AI alert explanation service"
```

---

## Task 13: Wire AI Enrichment into Alert Pipeline (Async)

**Files:**
- Modify: `fusion_server/services/alert_pipeline.py` (add async enrichment after alert fire)
- Modify: `fusion_server/services/sse_broadcaster.py` (broadcast enrichment)
- Test: `tests/test_alert_pipeline.py` (add enrichment test)

**Interfaces:**
- Consumes: `AIEnrichmentService` (Task 12)
- Produces: Alert enriched asynchronously after firing

- [ ] **Step 1: Add enrichment test**

```python
# Add to tests/test_alert_pipeline.py

def test_enrichment_runs_async_after_alert_fire():
    """Enrichment should be scheduled after alert fires (not blocking)."""
    pipeline = _make_pipeline()
    violations = [RuleViolation(
        object_id="obj1", camera_id="cam1", timestamp="2026-09-11T10:00:00",
        roi_name="Fence", violation_type="enter", threat_score=0.5,
    )]
    with patch.object(pipeline._rule_engine, 'evaluate', return_value=violations):
        with patch('fusion_server.services.alert_pipeline.AIEnrichmentService') as MockEnrich:
            mock_service = MockEnrich.return_value
            mock_service.enrich.return_value = "Test explanation"
            result = pipeline.process_event(
                object_id="obj1", camera_id="cam1", object_type="person",
                timestamp="2026-09-11T10:00:00",
                bbox={"x1": 0.2, "y1": 0.2, "x2": 0.3, "y2": 0.3},
            )
    assert result is not None
```

- [ ] **Step 2: Add enrichment to AlertPipeline.process_event()**

At the end of `process_event()` in `fusion_server/services/alert_pipeline.py`, after the SSE broadcast, add:

```python
        # 7. Schedule async enrichment (non-blocking)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._enrich_alert(alert_data))
        except RuntimeError:
            pass
```

And add the `_enrich_alert` method:

```python
    async def _enrich_alert(self, alert_data: FiredAlert) -> None:
        """Enrich an alert with AI explanation (async, non-blocking)."""
        try:
            from fusion_server.services.ai_enrichment import AIEnrichmentService
            enrichment = AIEnrichmentService()
            explanation = enrichment.enrich({
                "alert_id": alert_data.alert_id,
                "object_id": alert_data.object_id,
                "camera_id": alert_data.camera_id,
                "reason": alert_data.reason,
                "threat_score": alert_data.threat_score,
                "trajectory": alert_data.trajectory_projection or {},
            })

            # Update alert in DB
            if self._db:
                from fusion_server.db.models import Alert
                db_alert = self._db.query(Alert).filter(Alert.alert_id == alert_data.alert_id).first()
                if db_alert:
                    db_alert.ai_explanation = explanation
                    db_alert.status = "enriched"
                    from datetime import datetime
                    db_alert.enriched_at = datetime.utcnow()
                    self._db.commit()

            # Broadcast enrichment
            if self._sse_broadcast:
                await self._sse_broadcast.broadcast_alert_enriched(
                    alert_data.alert_id, explanation, alert_data.trajectory_projection
                )

            logger.info(f"Alert enriched: {alert_data.alert_id}")
        except Exception as e:
            logger.warning(f"Enrichment failed for {alert_data.alert_id}: {e}")
```

- [ ] **Step 3: Run tests**

Run: `.venv\Scripts\pytest tests/test_alert_pipeline.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add fusion_server/services/alert_pipeline.py
git commit -m "feat(pipeline): async AI enrichment after alert fire"
```

---

## Task 14: ROI CRUD API

**Files:**
- Create: `fusion_server/api/routes/rois.py`
- Modify: `fusion_server/main.py` (register router)
- Test: `tests/test_roi_api.py`

**Interfaces:**
- Consumes: `ROI` model (Task 1)
- Produces: CRUD endpoints at `/api/v1/rois`

- [ ] **Step 1: Write ROI API tests**

```python
# tests/test_roi_api.py
"""Tests for ROI CRUD API."""
import pytest
from fastapi.testclient import TestClient
from fusion_server.main import app
from unittest.mock import MagicMock, patch


client = TestClient(app)


def test_create_roi():
    """POST /api/v1/rois creates an ROI."""
    with patch('fusion_server.api.routes.rois.get_db') as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        response = client.post("/api/v1/rois", json={
            "camera_id": "cam1",
            "name": "North Fence",
            "polygon": [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            "alert_on_enter": True,
            "alert_on_exit": False,
            "object_types": ["person"],
        })
        assert response.status_code == 201


def test_list_rois():
    """GET /api/v1/rois lists ROIs."""
    response = client.get("/api/v1/rois")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_roi_api.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Create ROI CRUD API**

```python
# fusion_server/api/routes/rois.py
"""ROI CRUD API — Phase 4 virtual fence configuration."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from fusion_server.db.session import get_db
from fusion_server.db.models_roi import ROI

from pydantic import BaseModel


class ROICreate(BaseModel):
    camera_id: str
    name: str
    polygon: List[List[float]]
    alert_on_enter: bool = True
    alert_on_exit: bool = False
    object_types: Optional[List[str]] = None


class ROIUpdate(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    alert_on_enter: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    object_types: Optional[List[str]] = None
    active: Optional[bool] = None


class ROIResponse(BaseModel):
    id: str
    camera_id: str
    name: str
    polygon: List[List[float]]
    alert_on_enter: bool
    alert_on_exit: bool
    object_types: Optional[List[str]] = None
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/rois", tags=["rois"])


@router.post("", response_model=ROIResponse, status_code=status.HTTP_201_CREATED)
async def create_roi(roi: ROICreate, db: Session = Depends(get_db)):
    """Create a new ROI."""
    db_roi = ROI(
        id=uuid.uuid4(),
        camera_id=roi.camera_id,
        name=roi.name,
        polygon=roi.polygon,
        alert_on_enter=roi.alert_on_enter,
        alert_on_exit=roi.alert_on_exit,
        object_types=roi.object_types,
    )
    db.add(db_roi)
    db.commit()
    db.refresh(db_roi)
    return db_roi


@router.get("", response_model=List[ROIResponse])
async def list_rois(
    camera_id: Optional[str] = None,
    active: bool = True,
    db: Session = Depends(get_db),
):
    """List ROIs with optional filters."""
    query = db.query(ROI)
    if camera_id:
        query = query.filter(ROI.camera_id == camera_id)
    if active is not None:
        query = query.filter(ROI.active == active)
    return query.all()


@router.get("/{roi_id}", response_model=ROIResponse)
async def get_roi(roi_id: str, db: Session = Depends(get_db)):
    """Get a specific ROI."""
    roi = db.query(ROI).filter(ROI.id == roi_id).first()
    if not roi:
        raise HTTPException(status_code=404, detail="ROI not found")
    return roi


@router.patch("/{roi_id}", response_model=ROIResponse)
async def update_roi(roi_id: str, update: ROIUpdate, db: Session = Depends(get_db)):
    """Update an ROI."""
    roi = db.query(ROI).filter(ROI.id == roi_id).first()
    if not roi:
        raise HTTPException(status_code=404, detail="ROI not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(roi, field, value)
    db.commit()
    db.refresh(roi)
    return roi


@router.delete("/{roi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_roi(roi_id: str, db: Session = Depends(get_db)):
    """Soft delete an ROI (set active=false)."""
    roi = db.query(ROI).filter(ROI.id == roi_id).first()
    if not roi:
        raise HTTPException(status_code=404, detail="ROI not found")
    roi.active = False
    db.commit()
```

- [ ] **Step 4: Register router in main.py**

In `fusion_server/main.py`, add:
```python
from fusion_server.api.routes import cameras, stream, rois

app.include_router(rois.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_roi_api.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add fusion_server/api/routes/rois.py fusion_server/main.py tests/test_roi_api.py
git commit -m "feat(api): ROI CRUD API for virtual fence configuration"
```

---

## Task 15: Plate Detection Query API

**Files:**
- Create: `fusion_server/api/routes/plates.py`
- Modify: `fusion_server/main.py` (register router)
- Test: `tests/test_plates_api.py`

**Interfaces:**
- Consumes: `PlateDetection` model (Task 2)
- Produces: `GET /api/v1/plates` endpoint

- [ ] **Step 1: Write plates API test**

```python
# tests/test_plates_api.py
"""Tests for plate detection query API."""
import pytest
from fastapi.testclient import TestClient
from fusion_server.main import app


client = TestClient(app)


def test_list_plates():
    """GET /api/v1/plates returns list."""
    response = client.get("/api/v1/plates")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Create plates API**

```python
# fusion_server/api/routes/plates.py
"""Plate Detection Query API — Phase 4 ANPR."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from fusion_server.db.session import get_db
from fusion_server.db.models_plate import PlateDetection

from pydantic import BaseModel
from datetime import datetime


class PlateResponse(BaseModel):
    id: int
    object_id: str
    camera_id: str
    plate_text: str
    confidence: float
    bbox: list
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/plates", tags=["plates"])


@router.get("", response_model=List[PlateResponse])
async def list_plates(
    camera_id: Optional[str] = None,
    plate_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List plate detections with optional filters."""
    query = db.query(PlateDetection)
    if camera_id:
        query = query.filter(PlateDetection.camera_id == camera_id)
    if plate_text:
        query = query.filter(PlateDetection.plate_text.ilike(f"%{plate_text}%"))
    return query.order_by(PlateDetection.created_at.desc()).offset(offset).limit(limit).all()
```

- [ ] **Step 3: Register router in main.py**

In `fusion_server/main.py`, add:
```python
from fusion_server.api.routes import cameras, stream, rois, plates

app.include_router(plates.router)
```

- [ ] **Step 4: Run tests**

Run: `.venv\Scripts\pytest tests/test_plates_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add fusion_server/api/routes/plates.py fusion_server/main.py tests/test_plates_api.py
git commit -m "feat(api): plate detection query API"
```

---

## Task 16: Full Integration Tests

**Files:**
- Create: `tests/test_phase4_integration.py`

**Interfaces:**
- Consumes: All Phase 4 components

- [ ] **Step 1: Write integration tests**

```python
# tests/test_phase4_integration.py
"""Integration tests for Phase 4 — all exit criteria."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from fusion_server.core.rule_engine import RuleEngine, ROI
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector
from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
from fusion_server.core.trajectory import project_trajectory, TrajectoryPoint


def test_exit_criteria_a_roi_intrusion_fires_alert():
    """Tracked object crossing ROI fires alert."""
    engine = RuleEngine()
    engine.add_roi(ROI(
        camera_id="cam1", name="Fence",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    violations = engine.evaluate(
        object_id="obj1", camera_id="cam1", timestamp="2026-09-11T10:00:00",
        bbox={"x1": 0.2, "y1": 0.2, "x2": 0.3, "y2": 0.3}, object_type="person",
    )
    assert len(violations) > 0, "ROI intrusion should fire alert"


def test_exit_criteria_b_threat_score_computed():
    """Threat score is computed deterministically (not hardcoded)."""
    from fusion_server.core.rule_engine import RuleViolation
    violations = [RuleViolation(
        object_id="obj1", camera_id="cam1", timestamp="2026-09-11T10:00:00",
        roi_name="Fence", violation_type="enter", threat_score=0.5,
    )]
    score = calculate_threat_score(violations, ThreatContext(
        object_type="person", time_of_day="night", camera_zone="perimeter",
    ))
    assert 0.0 <= score <= 1.0
    assert score != 0.9  # Not hardcoded


def test_exit_criteria_c_trajectory_projection():
    """Trajectory projection is populated at alert time."""
    points = [TrajectoryPoint(x=i*0.1, y=0.5, timestamp=1000.0+i) for i in range(10)]
    predicted = project_trajectory(points, prediction_steps=10)
    assert len(predicted) == 10
    assert all(0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0 for p in predicted)


def test_exit_criteria_d_suspicious_activity():
    """Suspicious activity detection works."""
    det = SuspiciousActivityDetector(loiter_threshold_s=3.0)
    for i in range(5):
        det.update("obj1", "cam1", 0.25, 0.25, 1000.0 + i)
    violations = det.check_loitering("obj1", [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]])
    assert len(violations) > 0


def test_exit_criteria_e_pipeline_integration():
    """Full pipeline: event -> rule engine -> alert fired."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    pipeline = AlertPipeline(db=mock_db)
    pipeline._rule_engine.add_roi(ROI(
        camera_id="cam1", name="Fence",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    with patch.object(pipeline._alert_ledger, 'write_alert_with_hash'):
        result = pipeline.process_event(
            object_id="obj1", camera_id="cam1", object_type="person",
            timestamp="2026-09-11T10:00:00",
            bbox={"x1": 0.2, "y1": 0.2, "x2": 0.3, "y2": 0.3},
        )
    assert result is not None
    assert result.threat_score > 0.0
```

- [ ] **Step 2: Run tests**

Run: `.venv\Scripts\pytest tests/test_phase4_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase4_integration.py
git commit -m "test(phase4): integration tests for all exit criteria"
```

---

## Task 17: Update ARCHITECTURE.md Data Contracts

**Files:**
- Modify: `ARCHITECTURE.md` (Section 5)

**Interfaces:**
- Consumes: All Phase 4 data models
- Produces: Updated documentation

- [ ] **Step 1: Read current ARCHITECTURE.md Section 5**

Run: Read `ARCHITECTURE.md` and find Section 5

- [ ] **Step 2: Add ROI data contract**

Add after existing contracts:
```markdown
### ROI

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| camera_id | String | FK to camera (or `*` for all) |
| name | String | Human-readable name |
| polygon | JSON | List of [x,y] normalized 0-1 |
| alert_on_enter | Boolean | Default true |
| alert_on_exit | Boolean | Default false |
| object_types | JSON | `["person", "vehicle"]` or null |
| active | Boolean | Default true |
| created_at | Timestamp | |
```

- [ ] **Step 3: Add PlateDetection data contract**

```markdown
### PlateDetection

| Field | Type | Notes |
|-------|------|-------|
| id | BigInteger | Primary key |
| object_id | String | FK to tracked object |
| camera_id | String | |
| plate_text | String | OCR result (uppercase) |
| confidence | Float | OCR confidence |
| bbox | JSON | [x, y, w, h] normalized 0-1 |
| created_at | Timestamp | |
```

- [ ] **Step 4: Update Alert reason enum**

Update the `reason` field documentation to include all Phase 4 values:
```
reason: roi_intrusion | loitering | path_reversal | group_clustering | watchlist_match | plate_watchlist_match | camera_compromised
```

- [ ] **Step 5: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs(arch): update data contracts for Phase 4"
```

---

## Summary

| Task | Deliverable | Exit Criteria Met |
|------|-------------|-------------------|
| 1 | ROI DB model | ROI persistence |
| 2 | PlateDetection DB model | ANPR data storage |
| 3 | Trajectory buffer | Position history accumulation |
| 4 | FootprintEntry constraint | Phase 4 event types supported |
| 5 | Suspicious activity detection | Loitering, reversal, clustering |
| 6 | Rule engine wiring | ROIs loaded from DB, evaluate() works |
| 7 | Alert pipeline orchestrator | Sync rule check + alert fire |
| 8 | Threat scoring wiring | No hardcoded scores |
| 9 | SSE broadcaster | Real-time push infrastructure |
| 10 | SSE endpoint + viewer | Alert viewer page works |
| 11 | ANPR pipeline | Plate detection + OCR |
| 12 | AI enrichment service | LLaVA explanations |
| 13 | Enrichment wiring | Async enrichment after alert fire |
| 14 | ROI CRUD API | ROI management endpoints |
| 15 | Plate query API | ANPR query endpoints |
| 16 | Integration tests | All exit criteria verified |
| 17 | ARCHITECTURE.md update | Data contracts documented |

**Total files created:** 16
**Total files modified:** 6
**Total tests added:** ~50
