"""Cooldown wiring: AlertPipeline.process must dedup repeat violations
(525-alert flood fix) while keeping violations reported, and re-arm on exit.
Also: face/plate-only watchlist matches (object_id=None) must dedup on the
stable watchlist reference id, not a per-event-unique key."""
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np

from fusion_server.services.alert_pipeline import AlertPipeline
from fusion_server.services.cooldown_gate import get_cooldown_gate
from fusion_server.core.rule_engine import ROI


def _event(ts_minute, ts_second, bbox):
    return {
        "camera_id": "cam1",
        "object_id": "obj1",
        "object_type": "person",
        "timestamp": datetime(2025, 1, 1, 12, ts_minute, ts_second),
        "track_id": "trk1",
        "bbox": bbox,
        "confidence": 0.9,
    }


INSIDE = {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2}
OUTSIDE = {"x1": 0.8, "y1": 0.8, "x2": 0.9, "y2": 0.9}


def _mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None
    mock_db.query.return_value.order_by.return_value.first.return_value = None
    return mock_db


def _pipeline():
    p = AlertPipeline(db=_mock_db())
    p.rule_engine.add_roi(ROI(
        camera_id="cam1",
        name="Zone A",
        polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        alert_on_enter=True,
    ))
    return p


def test_repeat_violation_deduped_but_violations_still_reported():
    get_cooldown_gate().reset()
    p = _pipeline()

    r1 = p.process(_event(0, 0, INSIDE))
    assert len(r1["alerts"]) == 1
    assert len(r1["violations"]) == 1

    # 10s later, still inside: violation still detected, alert deduped
    r2 = p.process(_event(0, 10, INSIDE))
    assert len(r2["violations"]) == 1, "rule engine must still report the violation"
    assert len(r2["alerts"]) == 0, "second alert within 60s must be deduped"


def test_exit_rearm_refires_before_cooldown_elapsed():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    outside = p.process(_event(0, 20, OUTSIDE))
    assert outside["violations"] == []
    # Left and re-entered 5s after exit, well within 60s of first fire
    assert len(p.process(_event(0, 25, INSIDE))["alerts"]) == 1


def test_refires_after_cooldown_window():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    assert len(p.process(_event(1, 5, INSIDE))["alerts"]) == 1  # 65s later


def test_different_object_not_blocked():
    get_cooldown_gate().reset()
    p = _pipeline()

    assert len(p.process(_event(0, 0, INSIDE))["alerts"]) == 1
    other = dict(_event(0, 10, INSIDE), object_id="obj2")
    assert len(p.process(other)["alerts"]) == 1


def _one_hot(i: int, dim: int = 512):
    v = np.zeros(dim, dtype=np.float32)
    v[i] = 1.0
    return v.tolist()


def _post_face_event(client, track_id: str, timestamp: str, face):
    return client.post("/api/v1/events", json={
        "camera_id": "cam-wl-dedup",
        "timestamp": timestamp,
        "object_type": "person",
        "track_id": track_id,
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "face_embedding": face,
        "confidence": 0.9,
    })


def _watchlist_alerts(db_session):
    from fusion_server.db.models import Alert
    return db_session.query(Alert).filter(
        Alert.reason == "watchlist_match",
        Alert.camera_id == "cam-wl-dedup",
    ).all()


def test_face_only_watchlist_match_deduped_on_stable_reference(client, db_session):
    """Face-only matches have object_id=None; the gate must key on the stable
    watchlist reference_id. `unknown-{db_event.id}` is a fresh PK per event, so
    keying on it never dedups — one alert + ledger row per frame (the flood)."""
    face_a = _one_hot(0)
    face_b = _one_hot(1)  # orthogonal to face_a — no cross-match above 0.65

    for ref, face in (("wl-dedup-a", face_a), ("wl-dedup-b", face_b)):
        r = client.post("/api/v1/watchlist", json={
            "watchlist_type": "face",
            "reference_id": ref,
            "embedding": face,
        })
        assert r.status_code == 201, r.text

    assert _post_face_event(client, "t-wl-1", "2026-09-24T12:00:00", face_a).status_code == 201
    assert _post_face_event(client, "t-wl-2", "2026-09-24T12:00:10", face_a).status_code == 201

    alerts = _watchlist_alerts(db_session)
    assert len(alerts) == 1, (
        "repeat face-only match within 60s must be deduped "
        f"(gate key must be stable across events), got {len(alerts)}"
    )

    # A distinct watchlist reference must still fire inside the same window.
    assert _post_face_event(client, "t-wl-3", "2026-09-24T12:00:20", face_b).status_code == 201
    alerts = _watchlist_alerts(db_session)
    assert len(alerts) == 2, (
        f"distinct watchlist reference_id must produce its own alert, got {len(alerts)}"
    )
