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