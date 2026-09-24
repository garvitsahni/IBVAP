"""Cooldown wiring: AlertPipeline.process must dedup repeat violations
(525-alert flood fix) while keeping violations reported, and re-arm on exit."""
from datetime import datetime
from unittest.mock import MagicMock

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.cooldown_gate import get_cooldown_gate
from fusion_server.core.rule_engine import ROI


def _event(ts_minute, ts_second, bbox):
    return {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, ts_minute, ts_second),
        "track_id": "trk1",
        "bbox": bbox,
        "confidence": 0.9,
    }


INSIDE = {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}
OUTSIDE = {"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9}


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline():
    p = AlertPipeline(db=_mock_db())
    p.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return p


def test_repeat_violation_deduped_but_violations_still_reported():
    get_cooldown_gate().reset()
    p = _pipeline()

    r1 = p.process(_event(0, 0, INSIDE))
    assert len(r1["alerts"]) == 1
    assert len(r1["violations"]) == 1

    # 10s later, still inside: violation still detected, alert deduped
    r2 = p.process(_event(0, 10, INSIDE))
    assert len(r2["violations"]) == 1, "rule engine must still report the violation"
    assert len(r2["alerts"]) == 0, "second alert within 60s must be deduped"


def test_exit_rearm_refires_before_cooldown_elapsed():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    outside = p.process(_event(0, 20, OUTSIDE))
    assert outside["violations"] == []
    # Left and re-entered 5s after exit, well within 60s of first fire
    assert len(p.process(_event(0, 25, INSIDE))["alerts"]) == 1


def test_refires_after_cooldown_window():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    assert len(p.process(_event(1, 5, INSIDE))["alerts"]) == 1  # 65s later


def test_different_object_not_blocked():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    other = dict(_event(0, 10, INSIDE), object_id="obj2")
    assert len(p.process(other)["alerts"]) == 1
