"""Tests for the Alert Pipeline Orchestrator."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.core.rule_engine import RuleEngine, ROI, RuleViolation
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector
from fusion_server.core.trajectory import TrajectoryPoint


def _make_pipeline(**kwargs):
    return AlertPipeline(**kwargs)


def _make_event(**overrides):
    """Create a minimal detection event dict for pipeline processing."""
    event = {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    }
    event.update(overrides)
    return event


def _mock_db():
    """Create a mock DB session for alert tests."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    # For max_id query: return None (no existing alerts)
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


class TestAlertPipelineInit:
    """Pipeline initializes with all components."""

    def test_creates_default_components(self):
        pipeline = AlertPipeline()
        assert isinstance(pipeline.rule_engine, RuleEngine)
        assert isinstance(pipeline.trajectory_buffer, TrajectoryBuffer)
        assert isinstance(pipeline.suspicious_detector, SuspiciousActivityDetector)

    def test_uses_injected_components(self):
        engine = RuleEngine()
        buf = TrajectoryBuffer()
        det = SuspiciousActivityDetector()
        pipeline = AlertPipeline(
            rule_engine=engine,
            trajectory_buffer=buf,
            suspicious_detector=det,
        )
        assert pipeline.rule_engine is engine
        assert pipeline.trajectory_buffer is buf
        assert pipeline.suspicious_detector is det

    def test_sse_broadcaster_initially_none(self):
        pipeline = AlertPipeline()
        assert pipeline.sse_broadcaster is None

    def test_set_sse_broadcaster(self):
        pipeline = AlertPipeline()
        broadcaster = MagicMock()
        pipeline.set_sse_broadcaster(broadcaster)
        assert pipeline.sse_broadcaster is broadcaster


class TestPipelineProcessesEvent:
    """Pipeline processes a detection event through all stages."""

    def test_updates_trajectory_buffer(self):
        pipeline = AlertPipeline()
        event = _make_event()
        pipeline.process(event)
        history = pipeline.trajectory_buffer.get_history("obj1")
        assert len(history) == 1
        assert isinstance(history[0], TrajectoryPoint)

    def test_trajectory_buffer_receives_correct_coords(self):
        pipeline = AlertPipeline()
        event = _make_event(bbox={"x1": 0.3, "y1": 0.4, "x2": 0.5, "y2": 0.6})
        pipeline.process(event)
        history = pipeline.trajectory_buffer.get_history("obj1")
        point = history[0]
        assert point.x == pytest.approx(0.4)
        assert point.y == pytest.approx(0.5)

    def test_returns_result_with_violations_field(self):
        pipeline = AlertPipeline()
        event = _make_event()
        result = pipeline.process(event)
        assert "violations" in result
        assert "alerts" in result
        assert "trajectory_projection" in result
        assert "suspicious_activities" in result


class TestRuleEngineIntegration:
    """Pipeline runs rule engine checks on each event."""

    def test_no_violations_when_no_rois(self):
        pipeline = AlertPipeline()
        event = _make_event()
        result = pipeline.process(event)
        assert result["violations"] == []

    def test_violations_detected_with_matching_roi(self):
        pipeline = AlertPipeline()
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            alert_on_enter=True,
            object_types=["person"],
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert len(result["violations"]) == 1
        assert result["violations"][0].violation_type == "enter"

    def test_no_violations_for_wrong_camera(self):
        pipeline = AlertPipeline()
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam2",
            name="Zone B",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        event = _make_event(camera_id="cam1", bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert result["violations"] == []

    def test_no_violations_for_wrong_object_type(self):
        pipeline = AlertPipeline()
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone C",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            object_types=["vehicle"],
        ))
        event = _make_event(object_type="person", bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert result["violations"] == []


class TestAlertCreation:
    """Pipeline creates alerts when violations are found."""

    def test_creates_alert_for_violation(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            alert_on_enter=True,
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert len(result["alerts"]) == 1
        alert = result["alerts"][0]
        assert alert.status == "fired"
        assert alert.reason == "roi_intrusion"
        assert alert.threat_score >= 0.0

    def test_no_alert_without_violations(self):
        pipeline = AlertPipeline(db=_mock_db())
        event = _make_event()
        result = pipeline.process(event)
        assert result["alerts"] == []

    def test_alert_written_to_ledger(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            alert_on_enter=True,
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        alert = result["alerts"][0]
        assert alert.hash is not None
        assert len(alert.hash) == 64  # SHA-256 hex

    def test_alert_has_unique_id(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            alert_on_enter=True,
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        alert = result["alerts"][0]
        assert alert.alert_id is not None
        assert len(alert.alert_id) > 0


class TestThreatScoring:
    """Pipeline calculates threat scores via the scoring module."""

    def test_violation_gets_threat_score(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert result["alerts"][0].threat_score > 0.0

    def test_threat_score_is_float(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        score = result["alerts"][0].threat_score
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestTrajectoryProjection:
    """Pipeline projects trajectory when enough history exists."""

    def test_no_projection_with_few_points(self):
        pipeline = AlertPipeline()
        event = _make_event()
        result = pipeline.process(event)
        assert result["trajectory_projection"] == []

    def test_projection_after_enough_points(self):
        pipeline = AlertPipeline()
        for i in range(5):
            event = _make_event(
                bbox={"x1": 0.1 + i * 0.05, "y1": 0.1, "x2": 0.2 + i * 0.05, "y2": 0.2},
                timestamp=datetime(2025, 1, 1, 12, 0, i),
            )
            result = pipeline.process(event)
        assert len(result["trajectory_projection"]) > 0

    def test_projection_is_list_of_tuples(self):
        pipeline = AlertPipeline()
        for i in range(5):
            event = _make_event(
                bbox={"x1": 0.1 + i * 0.05, "y1": 0.1, "x2": 0.2 + i * 0.05, "y2": 0.2},
                timestamp=datetime(2025, 1, 1, 12, 0, i),
            )
            result = pipeline.process(event)
        for point in result["trajectory_projection"]:
            assert isinstance(point, tuple)
            assert len(point) == 2


class TestSSEBroadcaster:
    """Pipeline broadcasts alerts via SSE when broadcaster is set."""

    def test_broadcasts_when_set(self):
        pipeline = AlertPipeline(db=_mock_db())
        broadcaster = MagicMock()
        pipeline.set_sse_broadcaster(broadcaster)
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        pipeline.process(event)
        broadcaster.broadcast.assert_called_once()

    def test_no_broadcast_when_not_set(self):
        pipeline = AlertPipeline(db=_mock_db())
        pipeline.rule_engine.add_roi(ROI(
            camera_id="cam1",
            name="Zone A",
            polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        ))
        event = _make_event(bbox={"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2})
        result = pipeline.process(event)
        assert len(result["alerts"]) == 1  # Alert still created


class TestSuspiciousActivityDetection:
    """Pipeline checks for suspicious activity via trajectory data."""

    def test_suspicious_activities_field_always_present(self):
        pipeline = AlertPipeline()
        event = _make_event()
        result = pipeline.process(event)
        assert isinstance(result["suspicious_activities"], list)

    def test_suspicious_detector_receives_updates(self):
        pipeline = AlertPipeline()
        event = _make_event()
        pipeline.process(event)
        positions = pipeline.suspicious_detector._positions.get("obj1", [])
        assert len(positions) == 1
