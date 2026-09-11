"""Tests for watchlist matching integration in event pipeline."""
import numpy as np
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_event_with_matching_embedding_fires_watchlist_alert():
    """POST /api/v1/events with watchlist-matching embedding fires alert."""
    from fusion_server.main import app
    from fusion_server.core.watchlist_crypto import encrypt_embedding, get_key
    from fusion_server.db.models import Watchlist, DetectionEvent, Alert, FootprintEntry

    key = get_key()
    target_emb = np.random.rand(512).astype(np.float32)
    target_emb = target_emb / np.linalg.norm(target_emb)

    from fastapi.testclient import TestClient
    from fusion_server.db.session import get_db

    mock_db = MagicMock()
    mock_db._event_counter = 0

    # Track objects added to the mock DB
    added_objects = []

    def mock_add(obj):
        added_objects.append(obj)

    def mock_commit():
        pass

    def mock_refresh(obj):
        # Simulate SQLAlchemy refresh: set id and created_at on new objects
        if isinstance(obj, DetectionEvent) and obj.id is None:
            mock_db._event_counter += 1
            obj.id = mock_db._event_counter
            obj.created_at = datetime(2026, 9, 11, 10, 0, 0)

    mock_db.add = mock_add
    mock_db.commit = mock_commit
    mock_db.refresh = mock_refresh

    # Mock watchlist query
    mock_entry = MagicMock(spec=Watchlist)
    mock_entry.watchlist_type = "face"
    mock_entry.reference_id = "suspect-001"
    mock_entry.embedding = encrypt_embedding(target_emb.tolist(), key)
    mock_entry.active = True
    mock_entry.id = 1

    def mock_query(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.first.return_value = None
        if model is Watchlist:
            mock_q.all.return_value = [mock_entry]
        elif model is Alert:
            mock_q.all.return_value = []
        else:
            mock_q.all.return_value = []
        return mock_q

    mock_db.query = mock_query

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post("/api/v1/events", json={
            "camera_id": "cam1",
            "timestamp": "2026-09-11T10:00:00Z",
            "object_type": "person",
            "track_id": "track_001",
            "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
            "embedding": target_emb.tolist(),
            "confidence": 0.95,
        })
        assert response.status_code == 201
        data = response.json()
        assert "object_id" in data

        # Verify an Alert was added (watchlist match)
        alerts_added = [obj for obj in added_objects if isinstance(obj, Alert)]
        assert len(alerts_added) >= 1, "Expected at least one watchlist match alert"
        alert = alerts_added[0]
        assert alert.reason == "watchlist_match"
        assert alert.status == "fired"
    finally:
        app.dependency_overrides.clear()
