"""Tests for MatchingEngine — pgvector cosine similarity matching."""
import numpy as np
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


def test_matching_engine_initializes():
    """MatchingEngine can be instantiated."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.65, threshold_vehicle=0.60)
    assert engine.threshold_person == 0.65
    assert engine.threshold_vehicle == 0.60


def test_matching_engine_cosine_similarity():
    """MatchingEngine computes cosine similarity correctly."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(1.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(0.0)

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([-1.0, 0.0, 0.0])
    assert engine._cosine_similarity(a, b) == pytest.approx(-1.0)


def test_matching_engine_new_object():
    """MatchingEngine creates new object_id when no match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam1",
        timestamp=datetime.utcnow(),
    )

    assert object_id is not None
    assert len(object_id) > 0


def test_matching_engine_existing_match():
    """MatchingEngine returns existing object_id when match found."""
    from fusion_server.services.matching_engine import MatchingEngine
    engine = MatchingEngine(threshold_person=0.5)  # Low threshold for test

    embedding = np.random.rand(512).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    mock_event = MagicMock()
    mock_event.object_id = "existing-object-123"
    mock_event.embedding = embedding.tolist()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_event]

    object_id = engine.match_or_create(
        db=mock_db,
        embedding=embedding,
        object_type="person",
        camera_id="cam2",
        timestamp=datetime.utcnow(),
    )

    assert object_id == "existing-object-123"
