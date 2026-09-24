"""AlertResponse must return plate_text (silently omitted from all 5 manual
constructions — why AlertsPage never showed plates), plus new reason_detail
and snapshot_path fields."""
from datetime import datetime

import pytest

from fusion_server.db.models import Alert


@pytest.fixture
def full_alert(db_session):
    a = Alert(
        alert_id="fields-test-1",
        object_id="obj1",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion",
        status="fired",
        threat_score=0.6,
        plate_text="DL01AB1234",
        reason_detail='person entered ROI "Zone A" · score 0.60',
        snapshot_path="storage/alerts/fields-test-1.jpg",
    )
    db_session.add(a)
    db_session.commit()
    return a


def test_list_alerts_returns_all_view_fields(client, full_alert):
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["alert_id"] == "fields-test-1")
    assert row["plate_text"] == "DL01AB1234"
    assert row["reason_detail"] == 'person entered ROI "Zone A" · score 0.60'
    assert row["snapshot_path"] == "storage/alerts/fields-test-1.jpg"


def test_get_alert_returns_all_view_fields(client, full_alert):
    resp = client.get("/api/v1/alerts/fields-test-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plate_text"] == "DL01AB1234"
    assert body["reason_detail"].startswith("person entered")
    assert body["snapshot_path"].endswith(".jpg")


def test_acknowledge_response_returns_fields(client, full_alert):
    resp = client.post("/api/v1/alerts/fields-test-1/acknowledge")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plate_text"] == "DL01AB1234"
    assert "reason_detail" in body
    assert "snapshot_path" in body
