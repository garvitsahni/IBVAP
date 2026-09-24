"""Snapshot store: decode edge base64 thumbnail → JPEG on disk after broadcast
(best-effort; base64 never hits the DB; relative path persisted)."""
import base64
import os

import pytest

from fusion_server.db.models import Alert
from fusion_server.services import snapshot_store
from fusion_server.services.snapshot_store import (
    decode_jpeg_b64,
    get_snapshot_dir,
    save_alert_snapshots,
)


@pytest.fixture(autouse=True)
def isolated_snapshot_dir(tmp_path, monkeypatch):
    """Point the store at a temp dir for every test in this module."""
    monkeypatch.setenv("IBVAP_SNAPSHOT_DIR", str(tmp_path))
    yield tmp_path


def _tiny_jpeg_b64() -> str:
    """1x1 JPEG (SOI + EOI bytes) — decode gate only checks magic bytes."""
    raw = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
        0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
        0xFF, 0xD9,
    ])
    return base64.b64encode(raw).decode("ascii")


def test_get_snapshot_dir_env_override(tmp_path):
    assert get_snapshot_dir() == str(tmp_path)


def test_decode_rejects_non_jpeg():
    bad = base64.b64encode(b"not a jpeg at all").decode("ascii")
    with pytest.raises(ValueError):
        decode_jpeg_b64(bad)


def test_decode_rejects_invalid_base64():
    with pytest.raises(ValueError):
        decode_jpeg_b64("!!!not-base64!!!")


def test_decode_returns_jpeg_bytes():
    data = decode_jpeg_b64(_tiny_jpeg_b64())
    assert data[:2] == b"\xff\xd8"


def test_save_writes_file_and_returns_relative_path(tmp_path):
    path = save_alert_snapshots(["snap-ok-1"], _tiny_jpeg_b64())
    assert path == "storage/alerts/snap-ok-1.jpg"
    on_disk = tmp_path / "snap-ok-1.jpg"
    assert on_disk.is_file()
    assert on_disk.read_bytes()[:2] == b"\xff\xd8"


def test_save_never_raises_on_bad_payload(tmp_path):
    assert save_alert_snapshots(["snap-bad-1"], "not-valid-b64!!!") is None
    assert not (tmp_path / "snap-bad-1.jpg").exists()


def test_save_never_raises_on_unwritable_dir(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(snapshot_store.os, "makedirs", _boom)
    assert save_alert_snapshots(["snap-err-1"], _tiny_jpeg_b64()) is None


def test_save_with_empty_snapshot_is_noop(tmp_path):
    assert save_alert_snapshots(["snap-none-1"], None) is None
    assert not (tmp_path / "snap-none-1.jpg").exists()


def test_snapshot_get_endpoint(client, db_session):
    """200 with image/jpeg when file exists; 404 when snapshot_path is NULL."""
    import tempfile, time
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8fakejpg\xff\xd9")
        tmp_file = f.name

    alert = Alert(
        alert_id="snap-api-1", object_id="o", camera_id="c",
        timestamp=__import__("datetime").datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion", status="fired", threat_score=0.5,
        snapshot_path=tmp_file,
    )
    db_session.add(alert)
    no_snap = Alert(
        alert_id="snap-api-none", object_id="o", camera_id="c",
        timestamp=__import__("datetime").datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion", status="fired", threat_score=0.5,
        snapshot_path=None,
    )
    db_session.add(no_snap)
    db_session.commit()

    resp = client.get("/api/v1/alerts/snap-api-1/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/jpeg")

    assert client.get("/api/v1/alerts/snap-api-none/snapshot").status_code == 404
    assert client.get("/api/v1/alerts/does-not-exist/snapshot").status_code == 404

    os.unlink(tmp_file)


# --- Fix-round additions: root agreement, endpoint branches, wiring (review) ---

def test_default_store_dir_matches_serve_root(monkeypatch):
    """Review Important #1: store's DEFAULT write dir must equal the root the
    serve endpoint resolves `storage/alerts/...` against (no env override)."""
    monkeypatch.delenv("IBVAP_SNAPSHOT_DIR", raising=False)
    from fusion_server.api import alerts as alerts_mod
    serve_root = os.path.abspath(
        os.path.join(os.path.dirname(alerts_mod.__file__), "..", "..")
    )
    assert snapshot_store.get_snapshot_dir() == os.path.join(
        serve_root, "storage", "alerts"
    )


def test_default_config_save_then_endpoint_200(client, db_session, monkeypatch):
    """E2E with DEFAULT config: store writes where the endpoint serves from →
    200 image/jpeg. Catches write-dir/serve-root disagreement end to end."""
    from datetime import datetime
    monkeypatch.delenv("IBVAP_SNAPSHOT_DIR", raising=False)
    alert_id = "snap-e2e-default-1"
    store_dir = snapshot_store.get_snapshot_dir()
    # legacy (pre-fix) wrong location — cleaned up if a failing run wrote there
    legacy_dir = os.path.abspath(os.path.join(
        os.path.dirname(snapshot_store.__file__), "..", "storage", "alerts"
    ))
    try:
        rel = save_alert_snapshots([alert_id], _tiny_jpeg_b64())
        assert rel == f"storage/alerts/{alert_id}.jpg"
        db_session.add(Alert(
            alert_id=alert_id, object_id="o", camera_id="c",
            timestamp=datetime(2026, 9, 23, 12, 0, 0),
            reason="roi_intrusion", status="fired", threat_score=0.5,
            snapshot_path=rel,
        ))
        db_session.commit()

        resp = client.get(f"/api/v1/alerts/{alert_id}/snapshot")
        assert resp.status_code == 200, (
            f"expected 200; store wrote to {store_dir!r} but endpoint serves "
            f"relative path against the repo root — roots disagree?"
        )
        assert resp.headers["content-type"].startswith("image/jpeg")
        assert resp.content[:2] == b"\xff\xd8"
    finally:
        for d in (store_dir, legacy_dir):
            p = os.path.join(d, f"{alert_id}.jpg")
            if os.path.isfile(p):
                os.unlink(p)


def test_save_never_raises_on_non_sequence_ids():
    """Review minor: `alert_ids[0]` must be inside the try — never-raise
    contract must hold for non-sequence truthy input too."""
    assert save_alert_snapshots(123, _tiny_jpeg_b64()) is None


def _add_alert(db_session, alert_id, snapshot_path):
    from datetime import datetime
    db_session.add(Alert(
        alert_id=alert_id, object_id="o", camera_id="c",
        timestamp=datetime(2026, 9, 23, 12, 0, 0),
        reason="roi_intrusion", status="fired", threat_score=0.5,
        snapshot_path=snapshot_path,
    ))
    db_session.commit()


def test_endpoint_relative_path_file_missing_404(client, db_session):
    """Relative path recorded but file gone → 404, not a 500 / silent serve."""
    _add_alert(db_session, "snap-rel-missing",
               "storage/alerts/no-such-file-xyz.jpg")
    assert client.get(
        "/api/v1/alerts/snap-rel-missing/snapshot"
    ).status_code == 404


def test_endpoint_traversal_inside_root_404(client, db_session):
    """`storage/alerts/../../etc/passwd` must never be served (404)."""
    _add_alert(db_session, "snap-trav-1",
               "storage/alerts/../../etc/passwd")
    assert client.get(
        "/api/v1/alerts/snap-trav-1/snapshot"
    ).status_code == 404


def test_endpoint_traversal_escapes_root_404(client, db_session):
    """Traversal resolving OUTSIDE the repo root → explicit guard → 404."""
    _add_alert(db_session, "snap-trav-2",
               "storage/alerts/../../../../etc/passwd")
    assert client.get(
        "/api/v1/alerts/snap-trav-2/snapshot"
    ).status_code == 404


@pytest.fixture
async def async_client(db_session):
    """ASGI client with the test DB override (mirrors test_alert_sse_wiring)."""
    from httpx import ASGITransport, AsyncClient
    from fusion_server.main import app
    from fusion_server.db.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_post_event_with_snapshot_wires_store_and_row(
    async_client, db_session, monkeypatch
):
    """Review minor: real ingest wiring — POST /events with `snapshot` must
    schedule the real store (file on disk) AND persist snapshot_path on the
    alert row. No store mocks; SessionLocal adapted to the test session so
    _persist_snapshot's fresh session sees fixture rows (the test DB is a
    per-test uncommitted transaction; production SessionLocal binds elsewhere).
    """
    import asyncio
    import numpy as np

    emb = np.random.randn(512)
    emb = emb / np.linalg.norm(emb)

    resp = await async_client.post("/api/v1/watchlist", json={
        "watchlist_type": "face",
        "reference_id": "snap-wl-1",
        "embedding": emb.tolist(),
    })
    assert resp.status_code == 201, resp.text

    monkeypatch.setattr(
        "fusion_server.db.session.SessionLocal", lambda: db_session
    )

    resp = await async_client.post("/api/v1/events", json={
        "camera_id": "cam-snap",
        "timestamp": "2026-09-23T12:10:00",
        "object_type": "person",
        "track_id": "t-snap-wire-1",
        "bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.2, "y2": 0.2},
        "face_embedding": emb.tolist(),
        "confidence": 0.9,
        "snapshot": _tiny_jpeg_b64(),
    })
    assert resp.status_code == 201, resp.text

    from fusion_server.db.models import Alert as AlertRow
    row = None
    for _ in range(60):  # up to ~3s for ensure_future → executor → DB update
        db_session.expire_all()
        row = (db_session.query(AlertRow)
               .filter(AlertRow.camera_id == "cam-snap",
                       AlertRow.reason == "watchlist_match")
               .order_by(AlertRow.id.desc()).first())
        if row is not None and row.snapshot_path:
            break
        await asyncio.sleep(0.05)

    assert row is not None, "watchlist alert row never created"
    assert row.snapshot_path == f"storage/alerts/{row.alert_id}.jpg"
    from pathlib import Path
    on_disk = Path(os.environ["IBVAP_SNAPSHOT_DIR"]) / f"{row.alert_id}.jpg"
    assert on_disk.is_file(), f"JPEG not written to {on_disk}"
    assert on_disk.read_bytes()[:2] == b"\xff\xd8"

