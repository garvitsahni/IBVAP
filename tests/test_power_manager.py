"""Tests for PowerManager — low-power fallback mode."""
import pytest
from unittest.mock import patch, MagicMock
from fusion_server.services.power_manager import PowerManager


def test_power_manager_initializes_normal():
    """PowerManager starts in 'normal' mode."""
    pm = PowerManager()
    assert pm.get_mode() == "normal"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_reduced(mock_psutil):
    """High CPU triggers 'reduced' mode."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_critical(mock_psutil):
    """Very high CPU triggers 'critical' mode."""
    mock_psutil.cpu_percent.return_value = 97.0
    mock_mem = MagicMock()
    mock_mem.percent = 95.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "critical"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_recovers(mock_psutil):
    """Low load after reduced triggers recovery to normal."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"

    mock_psutil.cpu_percent.return_value = 30.0
    mock_mem.percent = 50.0
    for _ in range(7):
        pm.check_and_update()
    assert pm.get_mode() == "normal"


def test_camera_priority_by_roi_area():
    """Cameras with larger ROI are higher priority."""
    pm = PowerManager()
    cameras = [
        {"camera_id": "cam1", "roi_area_pct": 10},
        {"camera_id": "cam2", "roi_area_pct": 50},
        {"camera_id": "cam3", "roi_area_pct": 30},
    ]
    affected = pm.get_affected_cameras(cameras, target_count=1)
    assert "cam2" not in affected  # highest priority kept
    assert "cam1" in affected  # lowest priority dropped


def test_mode_callback():
    """Mode change fires callback."""
    cb = MagicMock()
    pm = PowerManager(mode_callback=cb)
    with patch("fusion_server.services.power_manager.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 85.0
        mock_mem = MagicMock()
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem
        pm.check_and_update()
    cb.assert_called_with("normal", "reduced", "cpu_85%")
