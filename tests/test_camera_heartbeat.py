"""Tests for camera heartbeat and staleness detection."""
import pytest
from datetime import datetime, timedelta
from fusion_server.services.camera_health_store import CameraHealthStore


def test_heartbeat_updates_last_seen():
    """heartbeat() sets last_seen to current time."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    last_seen = store.get_last_seen("cam1")
    assert last_seen is not None
    assert (datetime.utcnow() - last_seen).total_seconds() < 2.0


def test_heartbeat_does_not_overwrite_health():
    """heartbeat() preserves existing health status."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok", "ssim": 0.9})
    store.heartbeat("cam1")
    health = store.get("cam1")
    assert health["status"] == "ok"
    assert health["ssim"] == 0.9


def test_is_stale_returns_false_when_recent():
    """is_stale() returns False if last_seen is within threshold."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    assert store.is_stale("cam1", threshold_seconds=60) is False


def test_is_stale_returns_true_when_old():
    """is_stale() returns True if last_seen exceeds threshold."""
    store = CameraHealthStore()
    store.heartbeat("cam1")
    # Manually backdate last_seen
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)
    assert store.is_stale("cam1", threshold_seconds=60) is True


def test_is_stale_unknown_camera():
    """is_stale() returns True for unknown cameras (never heartbeat)."""
    store = CameraHealthStore()
    assert store.is_stale("unknown_cam", threshold_seconds=60) is True


def test_get_last_seen_unknown_camera():
    """get_last_seen() returns None for unknown cameras."""
    store = CameraHealthStore()
    assert store.get_last_seen("unknown_cam") is None
