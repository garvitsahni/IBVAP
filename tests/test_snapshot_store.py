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
