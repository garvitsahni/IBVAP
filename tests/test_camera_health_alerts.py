"""Tests for camera health endpoint and alert firing."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_camera_health_endpoint_updates_store():
    """POST /api/v1/cameras/{camera_id}/health updates CameraHealthStore."""
    from fusion_server.main import app
    client = TestClient(app)

    response = client.post("/api/v1/cameras/cam1/health", json={
        "status": "ok",
        "ssim": 0.87,
        "metric": None,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "cam1"
    assert data["status"] == "ok"


def test_camera_health_blinding_fires_alert():
    """POST /api/v1/cameras/cam1/health with blinding status fires alert."""
    from fusion_server.main import app
    from fusion_server.db.session import get_db

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("fusion_server.core.alert_ledger.AlertLedger.write_alert_with_hash") as mock_write:
            client = TestClient(app)

            response = client.post("/api/v1/cameras/cam1/health", json={
                "status": "blinding",
                "ssim": 0.0,
                "metric": 5.0,
            })
            assert response.status_code == 200
            data = response.json()
            assert data["alert_fired"] is True
            assert data["alert_reason"] == "camera_blinding"
            mock_write.assert_called_once()
    finally:
        app.dependency_overrides.clear()
