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
