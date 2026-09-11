"""Tests for ROI CRUD API — Phase 4 virtual fence management."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from fusion_server.main import app
from fusion_server.db.models_roi import ROI


@pytest.fixture()
def client(db_session):
    """Test client with DB dependency overridden."""
    from fusion_server.db.session import get_db

    def override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    with patch("fusion_server.main.init_db"):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


SAMPLE_POLYGON = [[0.1, 0.2], [0.3, 0.2], [0.3, 0.4], [0.1, 0.4]]


def _create_roi(client, **overrides):
    payload = {
        "camera_id": "cam1",
        "name": "North Fence",
        "polygon": SAMPLE_POLYGON,
    }
    payload.update(overrides)
    return client.post("/api/v1/rois", json=payload)


# ── CREATE ───────────────────────────────────────────────────────────────────


class TestCreateROI:
    def test_create_roi_returns_201(self, client):
        resp = _create_roi(client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["camera_id"] == "cam1"
        assert data["name"] == "North Fence"
        assert len(data["polygon"]) == 4
        assert data["alert_on_enter"] is True
        assert data["alert_on_exit"] is False
        assert data["active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_roi_with_all_fields(self, client):
        resp = _create_roi(
            client,
            alert_on_enter=False,
            alert_on_exit=True,
            object_types=["person", "vehicle"],
            active=False,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["alert_on_enter"] is False
        assert data["alert_on_exit"] is True
        assert data["object_types"] == ["person", "vehicle"]
        assert data["active"] is False

    def test_create_roi_wildcard_camera(self, client):
        resp = _create_roi(client, camera_id="*", name="Global Zone")
        assert resp.status_code == 201
        assert resp.json()["camera_id"] == "*"

    def test_create_roi_missing_name_fails(self, client):
        resp = client.post(
            "/api/v1/rois",
            json={"camera_id": "cam1", "polygon": SAMPLE_POLYGON},
        )
        assert resp.status_code == 422

    def test_create_roi_missing_polygon_fails(self, client):
        resp = client.post(
            "/api/v1/rois",
            json={"camera_id": "cam1", "name": "Test"},
        )
        assert resp.status_code == 422

    def test_create_roi_empty_polygon_fails(self, client):
        resp = client.post(
            "/api/v1/rois",
            json={"camera_id": "cam1", "name": "Test", "polygon": [[0.0, 0.0]]},
        )
        assert resp.status_code == 422


# ── READ ─────────────────────────────────────────────────────────────────────


class TestReadROI:
    def test_get_roi_by_id(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.get(f"/api/v1/rois/{roi_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == roi_id

    def test_get_roi_not_found(self, client):
        resp = client.get(
            "/api/v1/rois/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_list_rois_empty(self, client):
        resp = client.get("/api/v1/rois")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_rois_returns_all(self, client):
        _create_roi(client, name="ROI-1")
        _create_roi(client, name="ROI-2")
        resp = client.get("/api/v1/rois")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_rois_filter_camera_id(self, client):
        _create_roi(client, camera_id="cam1", name="ROI-1")
        _create_roi(client, camera_id="cam2", name="ROI-2")
        resp = client.get("/api/v1/rois", params={"camera_id": "cam1"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["camera_id"] == "cam1"

    def test_list_rois_filter_active(self, client):
        _create_roi(client, name="Active", active=True)
        _create_roi(client, name="Inactive", active=False)
        resp = client.get("/api/v1/rois", params={"active": False})
        assert len(resp.json()) == 1
        assert resp.json()[0]["active"] is False


# ── UPDATE ───────────────────────────────────────────────────────────────────


class TestUpdateROI:
    def test_update_name(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.put(f"/api/v1/rois/{roi_id}", json={"name": "South Gate"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "South Gate"

    def test_update_polygon(self, client):
        roi_id = _create_roi(client).json()["id"]
        new_poly = [[0.5, 0.5], [0.8, 0.5], [0.8, 0.8], [0.5, 0.8]]
        resp = client.put(f"/api/v1/rois/{roi_id}", json={"polygon": new_poly})
        assert resp.status_code == 200
        assert resp.json()["polygon"] == new_poly

    def test_update_alert_flags(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.put(
            f"/api/v1/rois/{roi_id}",
            json={"alert_on_enter": False, "alert_on_exit": True},
        )
        assert resp.status_code == 200
        assert resp.json()["alert_on_enter"] is False
        assert resp.json()["alert_on_exit"] is True

    def test_update_object_types(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.put(
            f"/api/v1/rois/{roi_id}", json={"object_types": ["vehicle"]}
        )
        assert resp.status_code == 200
        assert resp.json()["object_types"] == ["vehicle"]

    def test_update_active(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.put(f"/api/v1/rois/{roi_id}", json={"active": False})
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_update_not_found(self, client):
        resp = client.put(
            "/api/v1/rois/00000000-0000-0000-0000-000000000000",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_partial_update_preserves_other_fields(self, client):
        roi_id = _create_roi(client, object_types=["person"]).json()["id"]
        resp = client.put(f"/api/v1/rois/{roi_id}", json={"name": "Updated"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["object_types"] == ["person"]
        assert data["camera_id"] == "cam1"


# ── DELETE ───────────────────────────────────────────────────────────────────


class TestDeleteROI:
    def test_delete_roi_returns_204(self, client):
        roi_id = _create_roi(client).json()["id"]
        resp = client.delete(f"/api/v1/rois/{roi_id}")
        assert resp.status_code == 204

    def test_delete_roi_removes_from_list(self, client):
        roi_id = _create_roi(client).json()["id"]
        client.delete(f"/api/v1/rois/{roi_id}")
        resp = client.get("/api/v1/rois")
        assert len(resp.json()) == 0

    def test_delete_roi_not_found(self, client):
        resp = client.delete(
            "/api/v1/rois/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    def test_delete_roi_cannot_get_after(self, client):
        roi_id = _create_roi(client).json()["id"]
        client.delete(f"/api/v1/rois/{roi_id}")
        resp = client.get(f"/api/v1/rois/{roi_id}")
        assert resp.status_code == 404
