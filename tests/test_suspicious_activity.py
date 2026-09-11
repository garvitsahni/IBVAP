"""Tests for suspicious activity detection rules."""
import pytest
import math
from fusion_server.core.suspicious_activity import SuspiciousActivityDetector, SuspiciousActivity


def _make_detector(**kwargs):
    return SuspiciousActivityDetector(**kwargs)


def _add_points(detector, object_id, points, camera_id="cam1"):
    """Helper to add trajectory points."""
    for i, (x, y) in enumerate(points):
        detector.update(object_id, camera_id, x, y, 1000.0 + i)


def test_loitering_dwell_triggers():
    """Object inside ROI for > threshold triggers loitering alert."""
    det = _make_detector(loiter_threshold_s=5.0)
    # ROI: [0.0, 0.0] to [0.5, 0.5]
    roi_polygon = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    # Add 6 points inside ROI (1 per second, threshold 5s)
    points = [(0.25, 0.25)] * 6
    _add_points(det, "obj1", points)
    violations = det.check_loitering("obj1", roi_polygon)
    assert len(violations) == 1
    assert violations[0].activity_type == "loitering"
    assert violations[0].duration_s >= 5.0


def test_loitering_no_trigger_under_threshold():
    """Object inside ROI for < threshold does not trigger."""
    det = _make_detector(loiter_threshold_s=10.0)
    roi_polygon = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    points = [(0.25, 0.25)] * 5
    _add_points(det, "obj1", points)
    violations = det.check_loitering("obj1", roi_polygon)
    assert len(violations) == 0


def test_path_reversal_triggers():
    """Heading change > 90 degrees triggers path reversal."""
    det = _make_detector(reversal_angle_deg=90.0, reversal_window_s=5.0)
    # Walk north, then south
    points = [(0.5, 0.1), (0.5, 0.2), (0.5, 0.3),  # heading north
              (0.5, 0.2), (0.5, 0.1)]  # heading south (reversal)
    _add_points(det, "obj1", points)
    violations = det.check_path_reversal("obj1")
    assert len(violations) >= 1
    assert violations[0].activity_type == "path_reversal"


def test_path_reversal_no_trigger_small_angle():
    """Heading change < 90 degrees does not trigger."""
    det = _make_detector(reversal_angle_deg=90.0, reversal_window_s=10.0)
    # Walk northeast, then east (small angle change)
    points = [(0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.35), (0.5, 0.38)]
    _add_points(det, "obj1", points)
    violations = det.check_path_reversal("obj1")
    assert len(violations) == 0


def test_group_clustering_triggers():
    """N objects within radius for > threshold triggers clustering alert."""
    det = _make_detector(cluster_min_count=3, cluster_radius=0.1, cluster_threshold_s=3.0)
    # Three objects close together for 4 seconds
    for obj_id in ["obj1", "obj2", "obj3"]:
        for i in range(4):
            det.update(obj_id, "cam1", 0.5, 0.5, 1000.0 + i)
    violations = det.check_group_clustering()
    assert len(violations) >= 1
    assert violations[0].activity_type == "group_clustering"
