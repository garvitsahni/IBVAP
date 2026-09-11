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
