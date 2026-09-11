"""Tests for DetectorFallback — model tier switching."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fusion_server.services.detector_fallback import DetectorFallback


def test_fallback_initializes_at_normal():
    """DetectorFallback starts at 'normal' tier."""
    fb = DetectorFallback()
    assert fb.get_current_tier() == "normal"


def test_fallback_switches_to_degraded():
    """High latency triggers degraded tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "degraded"


def test_fallback_switches_to_critical():
    """Very high latency triggers critical tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=600, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "critical"


def test_fallback_high_queue_depth():
    """High queue depth triggers degraded tier."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=50, queue_depth=15, errors=0)
    assert fb.get_current_tier() == "degraded"


def test_fallback_high_error_rate():
    """High error rate triggers critical tier."""
    fb = DetectorFallback()
    for _ in range(10):
        fb.report_metrics(latency_ms=50, queue_depth=2, errors=1)
    assert fb.get_current_tier() == "critical"


def test_fallback_recovers_to_normal():
    """Good metrics after degraded triggers recovery."""
    fb = DetectorFallback()
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    assert fb.get_current_tier() == "degraded"
    for _ in range(5):
        fb.report_metrics(latency_ms=50, queue_depth=2, errors=0)
    assert fb.get_current_tier() == "normal"


def test_fallback_tier_callback():
    """Tier change fires callback."""
    cb = MagicMock()
    fb = DetectorFallback(tier_callback=cb)
    for _ in range(5):
        fb.report_metrics(latency_ms=250, queue_depth=5, errors=0)
    cb.assert_called_with("normal", "degraded", "latency_250ms_avg")


def test_motion_detection_returns_empty_list():
    """Motion detection on static frame returns no detections."""
    import numpy as np
    from edge.detector import motion_detection
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    prev_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    dets = motion_detection(frame, prev_frame)
    assert dets == []


def test_motion_detection_finds_movement():
    """Motion detection on different frames returns detections."""
    import numpy as np
    from edge.detector import motion_detection
    prev_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame = prev_frame.copy()
    frame[50:100, 50:100] = 255  # bright region
    dets = motion_detection(frame, prev_frame)
    assert len(dets) > 0
    assert "bbox" in dets[0]
    assert "confidence" in dets[0]