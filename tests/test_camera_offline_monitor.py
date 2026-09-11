"""Tests for CameraOfflineMonitor."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from fusion_server.services.camera_health_store import CameraHealthStore
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor


@pytest.fixture
def store():
    return CameraHealthStore()


@pytest.fixture
def mock_broadcaster():
    b = MagicMock()
    b.broadcast_camera_status_changed = AsyncMock()
    return b


@pytest.fixture
def mock_ledger():
    return MagicMock()


def test_monitor_initializes():
    """CameraOfflineMonitor can be instantiated."""
    store = CameraHealthStore()
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    assert monitor is not None


def test_online_camera_not_flagged():
    """Camera with recent heartbeat is not flagged offline."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    statuses = monitor.get_statuses()
    assert statuses.get("cam1") == "online"


def test_stale_camera_flagged_offline():
    """Camera with old heartbeat is flagged offline."""
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    # Backdate last_seen
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock(), heartbeat_interval=30)
    statuses = monitor.get_statuses()
    assert statuses.get("cam1") == "offline"


def test_unknown_camera_flagged_offline():
    """Camera never seen has no status entry (not in store)."""
    store = CameraHealthStore()
    monitor = CameraOfflineMonitor(store, MagicMock(), MagicMock())
    statuses = monitor.get_statuses()
    assert statuses.get("unknown_cam") is None


@pytest.mark.asyncio
async def test_check_staleness_broadcasts_offline(store, mock_broadcaster, mock_ledger):
    """check_staleness() broadcasts when camera goes offline."""
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

    monitor = CameraOfflineMonitor(store, mock_broadcaster, mock_ledger, heartbeat_interval=30)
    monitor._last_statuses = {"cam1": "online"}  # was online
    await monitor._check_staleness()

    mock_broadcaster.broadcast_camera_status_changed.assert_called_once()
    call_args = mock_broadcaster.broadcast_camera_status_changed.call_args[0][0]
    assert call_args["camera_id"] == "cam1"
    assert call_args["status"] == "offline"


@pytest.mark.asyncio
async def test_check_staleness_suppresses_repeated_offline(store, mock_broadcaster, mock_ledger):
    """Repeated offline status does not re-broadcast within suppress window."""
    store.update("cam1", {"status": "ok"})
    store.heartbeat("cam1")
    store._cameras["cam1"]["last_seen"] = datetime.utcnow() - timedelta(seconds=120)

    monitor = CameraOfflineMonitor(store, mock_broadcaster, mock_ledger, heartbeat_interval=30)
    monitor._last_statuses = {"cam1": "online"}
    monitor._suppress_until = {"cam1": datetime.utcnow() + timedelta(seconds=60)}

    await monitor._check_staleness()
    mock_broadcaster.broadcast_camera_status_changed.assert_not_called()
