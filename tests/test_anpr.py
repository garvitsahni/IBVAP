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
