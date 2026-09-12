"""Tests for blind-spot computation."""
import pytest


def test_compute_blind_spots_returns_dict():
    from fusion_server.services.coverage import compute_blind_spots
    result = compute_blind_spots([], [])
    assert isinstance(result, dict)


def test_compute_blind_spots_with_roi():
    from fusion_server.services.coverage import compute_blind_spots
    cameras = [{"camera_id": "cam1", "fov_polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    from fusion_server.core.rule_engine import ROI
    rois = [ROI(camera_id="cam1", name="zone1", polygon=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]])]
    result = compute_blind_spots(cameras, rois)
    assert "cam1" in result
    assert "blind_spots" in result["cam1"]
    assert len(result["cam1"]["blind_spots"]) > 0


def test_compute_blind_spots_full_coverage():
    from fusion_server.services.coverage import compute_blind_spots
    cameras = [{"camera_id": "cam1", "fov_polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    from fusion_server.core.rule_engine import ROI
    rois = [ROI(camera_id="cam1", name="full", polygon=[[0, 0], [1, 0], [1, 1], [0, 1]])]
    result = compute_blind_spots(cameras, rois)
    assert result["cam1"]["is_fully_covered"] is True
