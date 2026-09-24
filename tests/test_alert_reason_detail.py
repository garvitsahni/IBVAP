"""reason_detail is generated deterministically at fire time (Rule 1: no ML)."""
from datetime import datetime
from unittest.mock import MagicMock

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.cooldown_gate import get_cooldown_gate
from fusion_server.core.rule_engine import ROI


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def test_pipeline_sets_reason_detail_with_roi_and_score():
    get_cooldown_gate().reset()
    p = AlertPipeline(db=_mock_db())
    p.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    result = p.process({
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "track_id": "trk1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "confidence": 0.9,
    })
    assert len(result["alerts"]) == 1
    detail = result["alerts"][0].reason_detail
    assert 'entered ROI "Zone A"' in detail
    assert "score " in detail
    assert "person" in detail
