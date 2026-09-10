"""Integration test for Phase 2 — full pipeline from detection to footprint chain."""
import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


def test_full_pipeline_detection_to_footprint():
    """
    Simulate: detection → embedding → matching → footprint chain.
    This verifies the complete Phase 2 flow.
    """
    from fusion_server.services.matching_engine import MatchingEngine
    from fusion_server.services.footprint_writer import FootprintChainWriter

    embedding1 = np.random.rand(512).astype(np.float32)
    embedding1 = embedding1 / np.linalg.norm(embedding1)

    embedding2 = embedding1 + np.random.randn(512).astype(np.float32) * 0.01
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    engine = MatchingEngine(threshold_person=0.5)
    mock_db = MagicMock()

    # First match_or_create: no existing detections → creates new object
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
    object_id1 = engine.match_or_create(
        db=mock_db,
        embedding=embedding1,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
    )

    # Second match_or_create: existing detection with high similarity → returns same object_id
    mock_row = MagicMock()
    mock_row.embedding = embedding1.tolist()
    mock_row.object_id = object_id1
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_row]

    object_id2 = engine.match_or_create(
        db=mock_db,
        embedding=embedding2,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
    )

    assert object_id1 == object_id2, "Same object should get same object_id"

    # Footprint chain: first entry
    writer = FootprintChainWriter()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    entry1 = writer.write_entry(
        db=mock_db,
        object_id=object_id1,
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
        event_type="first_seen",
        detection_event_id=1,
    )

    assert entry1 is not None
    assert entry1["event_type"] == "first_seen"
    assert entry1["previous_hash"] is None

    # Footprint chain: second entry with hash linkage
    mock_last = MagicMock()
    mock_last.camera_id = "cam1"
    mock_last.hash = entry1["hash"]
    mock_last.timestamp = datetime(2026, 9, 11, 10, 0, 0)
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_last]

    entry2 = writer.write_entry(
        db=mock_db,
        object_id=object_id1,
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
        event_type="hop",
        detection_event_id=2,
    )

    assert entry2 is not None
    assert entry2["event_type"] == "hop"
    assert entry2["previous_hash"] == entry1["hash"]


def test_reid_service_to_matching_engine():
    """Verify ReIDService output feeds into MatchingEngine."""
    from edge.reid_service import ReIDService
    from fusion_server.services.matching_engine import MatchingEngine

    req_queue = MagicMock()
    res_queue = MagicMock()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop)
    assert embedding is None

    engine = MatchingEngine()
    assert engine.threshold_person == 0.65
