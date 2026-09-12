"""Camera CRUD API tests."""
import pytest


class TestCameraCRUD:
    """Tests for POST/GET/PATCH/DELETE /api/v1/cameras."""

    def test_create_camera(self, client):
        resp = client.post("/api/v1/cameras", json={
            "camera_id": "cam-test-01",
            "name": "Test Camera",
            "source_type": "rtsp",
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "location": "Building A",
            "zone": "perimeter",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["camera_id"] == "cam-test-01"
        assert data["name"] == "Test Camera"
        assert data["source_type"] == "rtsp"
        assert data["rtsp_url"] == "rtsp://192.168.1.100:554/stream"
        assert data["location"] == "Building A"
        assert data["zone"] == "perimeter"
        assert data["is_active"] is True

    def test_create_camera_duplicate(self, client):
        client.post("/api/v1/cameras", json={
            "camera_id": "cam-dup",
            "name": "First",
            "source_type": "usb",
        })
        resp = client.post("/api/v1/cameras", json={
            "camera_id": "cam-dup",
            "name": "Second",
            "source_type": "usb",
        })
        assert resp.status_code == 409

    def test_create_camera_missing_fields(self, client):
        resp = client.post("/api/v1/cameras", json={"name": "No ID"})
        assert resp.status_code == 422

    def test_list_cameras(self, client):
        client.post("/api/v1/cameras", json={
            "camera_id": "cam-list-01",
            "name": "Camera One",
            "source_type": "hls",
        })
        resp = client.get("/api/v1/cameras")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        ids = [c["camera_id"] for c in data]
        assert "cam-list-01" in ids

    def test_get_camera(self, client):
        client.post("/api/v1/cameras", json={
            "camera_id": "cam-get",
            "name": "Get Me",
            "source_type": "webcam",
        })
        resp = client.get("/api/v1/cameras/cam-get")
        assert resp.status_code == 200
        assert resp.json()["camera_id"] == "cam-get"

    def test_get_camera_not_found(self, client):
        resp = client.get("/api/v1/cameras/nonexistent")
        assert resp.status_code == 404

    def test_update_camera(self, client):
        client.post("/api/v1/cameras", json={
            "camera_id": "cam-update",
            "name": "Original",
            "source_type": "usb",
        })
        resp = client.patch("/api/v1/cameras/cam-update", json={
            "name": "Updated Name",
            "location": "New Location",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["location"] == "New Location"
        assert data["source_type"] == "usb"  # unchanged

    def test_update_camera_not_found(self, client):
        resp = client.patch("/api/v1/cameras/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_camera(self, client):
        client.post("/api/v1/cameras", json={
            "camera_id": "cam-del",
            "name": "Delete Me",
            "source_type": "unknown",
        })
        resp = client.delete("/api/v1/cameras/cam-del")
        assert resp.status_code == 204
        # Verify deleted
        resp = client.get("/api/v1/cameras/cam-del")
        assert resp.status_code == 404

    def test_delete_camera_not_found(self, client):
        resp = client.delete("/api/v1/cameras/nonexistent")
        assert resp.status_code == 404

    def test_seed_local_camera(self, client):
        resp = client.post("/api/v1/cameras/seed-local")
        assert resp.status_code == 201
        data = resp.json()
        assert data["camera_id"] == "laptop-webcam"
        assert data["name"] == "Laptop Camera"
        assert data["source_type"] == "webcam"

    def test_seed_local_camera_idempotent(self, client):
        resp1 = client.post("/api/v1/cameras/seed-local")
        assert resp1.status_code == 201
        # Second call should return existing camera (200) or re-seed safely (201)
        resp2 = client.post("/api/v1/cameras/seed-local")
        assert resp2.status_code in (200, 201)
        data = resp2.json()
        assert data["camera_id"] == "laptop-webcam"
        assert data["name"] == "Laptop Camera"

    def test_health_endpoint_still_works(self, client):
        resp = client.get("/api/v1/cameras/health")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_heartbeat_still_works(self, client):
        resp = client.post("/api/v1/cameras/cam-hb-test/heartbeat")
        assert resp.status_code == 200
        assert resp.json()["camera_id"] == "cam-hb-test"

    def test_source_type_validation(self, client):
        resp = client.post("/api/v1/cameras", json={
            "camera_id": "cam-bad-type",
            "name": "Bad Type",
            "source_type": "invalid_type",
        })
        assert resp.status_code == 422
