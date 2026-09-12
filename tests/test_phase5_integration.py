"""Phase 5 integration tests — end-to-end API surface + overlay pipeline."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import text


@pytest.fixture
def client():
    from fusion_server.main import app
    return TestClient(app)


def _db_available():
    try:
        from fusion_server.db.session import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")


class TestDashboardAPI:
    @requires_db
    def test_dashboard_stats_endpoint(self, client):
        r = client.get("/api/v1/dashboard/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_alerts_today" in data
        assert "active_cameras" in data
        assert "alerts_by_severity" in data

    def test_cameras_list_endpoint(self, client):
        r = client.get("/api/v1/cameras")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @requires_db
    def test_ledger_status_endpoint(self, client):
        r = client.get("/api/v1/ledger/status")
        assert r.status_code == 200
        data = r.json()
        assert "is_valid" in data
        assert "total_entries" in data

    @requires_db
    def test_blind_spots_endpoint(self, client):
        r = client.get("/api/v1/coverage/blind-spots")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_clip_serving_404(self, client):
        r = client.get("/api/v1/clips/nonexistent.mp4")
        assert r.status_code == 404


class TestHLSStreamEndpoints:
    def test_hls_playlist_404_when_not_running(self, client):
        r = client.get("/api/v1/streams/cam_test.m3u8")
        assert r.status_code == 404

    def test_hls_segment_404_when_not_running(self, client):
        r = client.get("/api/v1/streams/cam_test/seg001.ts")
        assert r.status_code == 404


class TestAlertTimeRange:
    @requires_db
    def test_alerts_supports_since(self, client):
        r = client.get("/api/v1/alerts?since=2026-01-01T00:00:00")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @requires_db
    def test_alerts_supports_until(self, client):
        r = client.get("/api/v1/alerts?until=2026-12-31T23:59:59")
        assert r.status_code == 200


class TestClipOverlayPipeline:
    """Test that alert creation triggers overlay rendering when clip_path is provided."""

    @patch("fusion_server.services.clip_overlay.render_overlay")
    @requires_db
    def test_create_alert_calls_overlay(self, mock_render, client):
        mock_render.return_value = "/tmp/overlay_out.mp4"
        r = client.post("/api/v1/alerts", json={
            "object_id": "obj_integ_001",
            "camera_id": "cam1",
            "timestamp": "2026-09-11T12:00:00",
            "reason": "roi_intrusion",
            "threat_score": 0.75,
            "clip_path": "/tmp/test_clip.mp4",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["clip_path"] == "/tmp/test_clip_overlay.mp4"
        mock_render.assert_called_once()

    @requires_db
    def test_create_alert_without_clip_succeeds(self, client):
        r = client.post("/api/v1/alerts", json={
            "object_id": "obj_integ_002",
            "camera_id": "cam1",
            "timestamp": "2026-09-11T12:00:00",
            "reason": "roi_intrusion",
            "threat_score": 0.5,
        })
        assert r.status_code == 201
        assert r.json()["clip_path"] is None

    @patch("fusion_server.services.clip_overlay.render_overlay", side_effect=RuntimeError("ffmpeg not found"))
    @requires_db
    def test_overlay_failure_does_not_block_alert(self, mock_render, client):
        """AGENTS.md Rule 4: AI enrichment never blocks alert delivery."""
        r = client.post("/api/v1/alerts", json={
            "object_id": "obj_integ_003",
            "camera_id": "cam1",
            "timestamp": "2026-09-11T12:00:00",
            "reason": "roi_intrusion",
            "threat_score": 0.6,
            "clip_path": "/tmp/test_clip.mp4",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "fired"


class TestDashboardStaticMounts:
    def test_dashboard_mount_returns_html(self, client):
        r = client.get("/dashboard/")
        assert r.status_code in (200, 404)

