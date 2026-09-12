"""Tests for camera registry endpoint."""
import pytest


def test_camera_list_returns_200(client):
    response = client.get("/api/v1/cameras")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_camera_list_item_shape(client):
    # Register a camera via health endpoint
    client.post("/api/v1/cameras/cam1/health", json={
        "status": "ok", "ssim": 0.95
    })
    response = client.get("/api/v1/cameras")
    data = response.json()
    assert len(data) >= 1
    cam = data[0]
    assert "camera_id" in cam
    assert "status" in cam
