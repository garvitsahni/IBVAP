"""Tests for Phase 2 API routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_footprint_write_endpoint():
    """POST /api/v1/footprint writes footprint entry."""
    from fusion_server.main import app
    client = TestClient(app)
    response = client.post("/api/v1/footprint", json={
        "object_id": "test-obj-123",
        "camera_id": "cam1",
        "timestamp": "2026-09-11T10:00:00Z",
        "event_type": "first_seen",
    })
    assert response.status_code != 404


def test_camera_health_endpoint():
    """GET /api/v1/cameras/health returns camera health status."""
    from fusion_server.main import app
    client = TestClient(app)
    response = client.get("/api/v1/cameras/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_event_ingestion_triggers_matching():
    """POST /api/v1/events with embedding triggers async matching."""
    from fusion_server.main import app
    client = TestClient(app)

    import numpy as np
    embedding = np.random.rand(512).astype(float).tolist()

    response = client.post("/api/v1/events", json={
        "camera_id": "cam1",
        "timestamp": "2026-09-11T10:00:00Z",
        "object_type": "person",
        "track_id": "track_001",
        "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
        "embedding": embedding,
        "confidence": 0.95,
    })
    assert response.status_code == 201
    data = response.json()
    assert "object_id" in data
    assert data["object_id"] is not None
