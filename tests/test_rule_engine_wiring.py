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
