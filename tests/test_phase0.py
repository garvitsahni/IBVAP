import pytest
from sqlalchemy.orm import Session
from fusion_server.db.session import SessionLocal
from fusion_server.db.models import DetectionEvent, FootprintEntry, Alert, Watchlist
from fusion_server.core.ledger import compute_hash, verify_chain, append_entry
from fusion_server.core.rule_engine import RuleEngine, ROI, RuleViolation
from fusion_server.core.threat_scoring import calculate_threat_score, get_threat_level, ThreatContext
from fusion_server.core.trajectory import project_trajectory, TrajectoryPoint
from datetime import datetime
import uuid


@pytest.fixture
def db():
    """Database session fixture."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestLedgerIntegrity:
    """Test hash-chain ledger integrity (Phase 3 requirement)."""

    def test_compute_hash_deterministic(self):
        """Hash computation must be deterministic."""
        data = "test_data_123"
        hash1 = compute_hash(data)
        hash2 = compute_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_verify_chain_valid(self):
        """Valid chain should pass verification."""
        chain = [
            {"object_id": "obj1", "camera_id": "cam1", "timestamp": "2024-01-01T00:00:00", "event_type": "first_seen", "hash": "", "previous_hash": None},
            {"object_id": "obj1", "camera_id": "cam2", "timestamp": "2024-01-01T00:05:00", "event_type": "hop", "hash": "", "previous_hash": None},
            {"object_id": "obj1", "camera_id": "cam3", "timestamp": "2024-01-01T00:10:00", "event_type": "alert", "hash": "", "previous_hash": None},
        ]
        for i, entry in enumerate(chain):
            data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
            entry['hash'] = compute_hash(data + "footprint")
            if i > 0:
                entry['previous_hash'] = chain[i-1]['hash']

        is_valid, broken_idx = verify_chain(chain)
        assert is_valid is True
        assert broken_idx is None

    def test_verify_chain_tampered_data(self):
        """Tampered chain data should fail verification."""
        chain = [
            {"object_id": "obj1", "camera_id": "cam1", "timestamp": "2024-01-01T00:00:00", "event_type": "first_seen", "hash": "", "previous_hash": None},
            {"object_id": "obj1", "camera_id": "cam2", "timestamp": "2024-01-01T00:05:00", "event_type": "hop", "hash": "", "previous_hash": None},
        ]
        for i, entry in enumerate(chain):
            data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
            entry['hash'] = compute_hash(data + "footprint")
            if i > 0:
                entry['previous_hash'] = chain[i-1]['hash']

        # Tamper with camera_id
        chain[1]['camera_id'] = 'cam99'

        is_valid, broken_idx = verify_chain(chain)
        assert is_valid is False
        assert broken_idx == 1

    def test_verify_chain_tampered_previous_hash(self):
        """Tampered previous_hash should fail verification."""
        chain = [
            {"object_id": "obj1", "camera_id": "cam1", "timestamp": "2024-01-01T00:00:00", "event_type": "first_seen", "hash": "", "previous_hash": None},
            {"object_id": "obj1", "camera_id": "cam2", "timestamp": "2024-01-01T00:05:00", "event_type": "hop", "hash": "", "previous_hash": None},
        ]
        for i, entry in enumerate(chain):
            data = f"{entry['object_id']}{entry['camera_id']}{entry['timestamp']}{entry['event_type']}"
            entry['hash'] = compute_hash(data + "footprint")
            if i > 0:
                entry['previous_hash'] = chain[i-1]['hash']

        # Tamper previous_hash
        chain[1]['previous_hash'] = 'tampered_hash'

        is_valid, broken_idx = verify_chain(chain)
        assert is_valid is False
        assert broken_idx == 1

    def test_append_entry_links_correctly(self):
        """append_entry should create correct hash chain linkage."""
        entry1 = append_entry("obj1", "cam1", "2024-01-01T00:00:00", "first_seen", None)
        entry2 = append_entry("obj1", "cam2", "2024-01-01T00:05:00", "hop", entry1['hash'])

        assert entry2['previous_hash'] == entry1['hash']
        assert entry1['previous_hash'] is None

        # Verify the chain
        chain = [entry1, entry2]
        is_valid, _ = verify_chain(chain)
        assert is_valid is True


class TestRuleEngine:
    """Test deterministic rule engine (Phase 4 - no ML for alert decisions)."""

    def test_roi_intrusion_detection(self):
        """Test ROI intrusion detection with polygon geometry."""
        engine = RuleEngine()

        # Define a square ROI in center of frame (normalized 0-1)
        roi = ROI(
            camera_id="cam1",
            name="test_zone",
            polygon=[[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]],
            alert_on_enter=True,
        )
        engine.add_roi(roi)

        # Object entering ROI (centroid at 0.5, 0.5)
        bbox_inside = {"x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6}
        violations = engine.check_roi_intrusion(
            object_id="obj1",
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00",
            bbox=bbox_inside,
            object_type="person",
        )
        assert len(violations) == 1
        assert violations[0].violation_type == "enter"
        assert violations[0].roi_name == "test_zone"

    def test_roi_no_intrusion_outside(self):
        """Object outside ROI should not trigger violation."""
        engine = RuleEngine()

        roi = ROI(
            camera_id="cam1",
            name="test_zone",
            polygon=[[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]],
            alert_on_enter=True,
        )
        engine.add_roi(roi)

        # Object outside ROI (centroid at 0.1, 0.1)
        bbox_outside = {"x1": 0.05, "y1": 0.05, "x2": 0.15, "y2": 0.15}
        violations = engine.check_roi_intrusion(
            object_id="obj1",
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00",
            bbox=bbox_outside,
            object_type="person",
        )
        assert len(violations) == 0

    def test_roi_exit_detection(self):
        """Test exit detection when object leaves ROI."""
        engine = RuleEngine()

        roi = ROI(
            camera_id="cam1",
            name="test_zone",
            polygon=[[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]],
            alert_on_enter=False,
            alert_on_exit=True,
        )
        engine.add_roi(roi)

        # Object was inside, now outside
        prev_bbox = {"x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6}
        curr_bbox = {"x1": 0.05, "y1": 0.05, "x2": 0.15, "y2": 0.15}

        violations = engine.check_roi_intrusion(
            object_id="obj1",
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00",
            bbox=curr_bbox,
            object_type="person",
            previous_bbox=prev_bbox,
        )
        assert len(violations) == 1
        assert violations[0].violation_type == "exit"

    def test_roi_object_type_filter(self):
        """ROI should filter by object_type."""
        engine = RuleEngine()

        roi = ROI(
            camera_id="cam1",
            name="vehicle_only",
            polygon=[[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]],
            object_types=["vehicle"],
        )
        engine.add_roi(roi)

        # Person should not trigger
        bbox = {"x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6}
        violations = engine.check_roi_intrusion(
            object_id="obj1",
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00",
            bbox=bbox,
            object_type="person",
        )
        assert len(violations) == 0

        # Vehicle should trigger
        violations = engine.check_roi_intrusion(
            object_id="obj1",
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00",
            bbox=bbox,
            object_type="vehicle",
        )
        assert len(violations) == 1


class TestThreatScoring:
    """Test deterministic threat scoring (Phase 4 - no ML)."""

    def test_base_scores_by_violation_type(self):
        """Each violation type has deterministic base score."""
        from fusion_server.core.threat_scoring import VIOLATION_BASE_SCORES

        assert VIOLATION_BASE_SCORES["virtual_fence_crossing"] == 0.7
        assert VIOLATION_BASE_SCORES["enter"] == 0.5
        assert VIOLATION_BASE_SCORES["exit"] == 0.4

    def test_threat_score_calculation(self):
        """Threat score calculation is deterministic."""
        violations = [
            RuleViolation(
                object_id="obj1", camera_id="cam1", timestamp="2024-01-01T00:00:00",
                roi_name="perimeter", violation_type="virtual_fence_crossing", threat_score=0.7
            )
        ]
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
        )

        score = calculate_threat_score(violations, context)
        assert score == 0.7  # Base 0.7 * person(1.0) * day(1.0) * perimeter(1.0)

    def test_threat_score_night_multiplier(self):
        """Night time increases threat score."""
        violations = [
            RuleViolation(
                object_id="obj1", camera_id="cam1", timestamp="2024-01-01T00:00:00",
                roi_name="perimeter", violation_type="enter", threat_score=0.5
            )
        ]
        context_day = ThreatContext(object_type="person", time_of_day="day", camera_zone="perimeter")
        context_night = ThreatContext(object_type="person", time_of_day="night", camera_zone="perimeter")

        score_day = calculate_threat_score(violations, context_day)
        score_night = calculate_threat_score(violations, context_night)

        assert score_night > score_day
        assert score_night == pytest.approx(score_day * 1.3, rel=0.01)

    def test_threat_score_watchlist_max(self):
        """Watchlist match should max threat score at 0.9+."""
        violations = [
            RuleViolation(
                object_id="obj1", camera_id="cam1", timestamp="2024-01-01T00:00:00",
                roi_name="perimeter", violation_type="enter", threat_score=0.3
            )
        ]
        context = ThreatContext(
            object_type="person",
            time_of_day="day",
            camera_zone="perimeter",
            is_watchlist_match=True,
        )

        score = calculate_threat_score(violations, context)
        assert score >= 0.9

    def test_threat_levels(self):
        """Threat level categorization."""
        assert get_threat_level(0.9) == "critical"
        assert get_threat_level(0.6) == "high"
        assert get_threat_level(0.4) == "medium"
        assert get_threat_level(0.1) == "low"
        assert get_threat_level(0.0) == "none"


class TestTrajectoryProjection:
    """Test Kalman filter trajectory projection."""

    def test_project_trajectory_minimum_points(self):
        """Need at least 2 points for projection."""
        points = [TrajectoryPoint(x=0.5, y=0.5, timestamp=1000.0)]
        result = project_trajectory(points, prediction_steps=5)
        assert result == []

    def test_project_trajectory_linear(self):
        """Linear trajectory should project forward."""
        points = [
            TrajectoryPoint(x=0.1, y=0.1, timestamp=1000.0),
            TrajectoryPoint(x=0.2, y=0.2, timestamp=1001.0),
            TrajectoryPoint(x=0.3, y=0.3, timestamp=1002.0),
        ]
        result = project_trajectory(points, prediction_steps=3, dt=1.0)

        assert len(result) == 3
        # Should continue in same direction
        assert result[0][0] > 0.3  # x continues increasing
        assert result[0][1] > 0.3  # y continues increasing

    def test_projection_clamped_to_bounds(self):
        """Projections should be clamped to [0, 1]."""
        points = [
            TrajectoryPoint(x=0.9, y=0.9, timestamp=1000.0),
            TrajectoryPoint(x=0.95, y=0.95, timestamp=1001.0),
        ]
        result = project_trajectory(points, prediction_steps=5, dt=1.0)

        for x, y in result:
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0


class TestDatabaseModels:
    """Test database model creation and relationships."""

    def test_detection_event_creation(self, db):
        """Test DetectionEvent creation."""
        event = DetectionEvent(
            camera_id="cam1",
            timestamp=datetime.utcnow(),
            object_type="person",
            track_id="track_001",
            bbox={"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
            embedding=None,
            confidence=0.95,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.id is not None
        assert event.camera_id == "cam1"
        assert event.object_type == "person"
        assert event.confidence == 0.95

    def test_footprint_chain_creation(self, db):
        """Test FootprintEntry chain creation."""
        # First entry
        entry1 = FootprintEntry(
            object_id="obj_001",
            camera_id="cam1",
            timestamp=datetime.utcnow(),
            event_type="first_seen",
            hash="hash1",
            previous_hash=None,
        )
        db.add(entry1)
        db.commit()
        db.refresh(entry1)

        # Second entry linked to first
        entry2 = FootprintEntry(
            object_id="obj_001",
            camera_id="cam2",
            timestamp=datetime.utcnow(),
            event_type="hop",
            hash="hash2",
            previous_hash="hash1",
        )
        db.add(entry2)
        db.commit()
        db.refresh(entry2)

        assert entry2.previous_hash == entry1.hash

    def test_alert_creation_defaults_to_fired(self, db):
        """Alert must default to 'fired' status per ARCHITECTURE.md."""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            object_id="obj_001",
            camera_id="cam1",
            timestamp=datetime.utcnow(),
            reason="virtual_fence_crossing",
            threat_score=0.7,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        assert alert.status == "fired"

    def test_watchlist_creation(self, db):
        """Test Watchlist entry creation."""
        entry = Watchlist(
            watchlist_type="face",
            reference_id="case_123",
            embedding=[0.1] * 512,
            metadata={"name": "Person of Interest"},
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.id is not None
        assert entry.watchlist_type == "face"
        assert entry.active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])