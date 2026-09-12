"""Tests for HLS manager."""
import pytest


def test_hls_manager_creates_instance():
    from fusion_server.services.hls_manager import HLSManager
    mgr = HLSManager()
    assert mgr is not None


def test_hls_manager_starts_stops():
    from fusion_server.services.hls_manager import HLSManager
    mgr = HLSManager(hls_dir="/tmp/test_hls")
    # Don't actually start FFmpeg, just test state management
    mgr._running["cam1"] = True
    assert mgr.is_running("cam1") is True
    assert mgr.is_running("cam2") is False
