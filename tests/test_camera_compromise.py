"""Tests for camera compromise detection heuristics."""
import numpy as np
import pytest


def test_darkness_detection_normal_frame():
    """Normal frame is not dark."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
    result = svc.check_darkness(frame)
    assert result["status"] == "ok"
    assert result["metric"] > 15


def test_darkness_detection_dark_frame():
    """Very dark frame is detected as blinding."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame = np.zeros((480, 640, 3), dtype=np.uint8) + 5
    result = svc.check_darkness(frame)
    assert result["status"] == "blinding"
    assert result["metric"] < 15


def test_blur_detection_sharp_frame():
    """Sharp frame is not blurry."""
    from edge.camera_health import CameraHealthService
    import cv2
    svc = CameraHealthService(camera_id="cam1")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (200, 200), (255, 255, 255), -1)
    cv2.rectangle(frame, (300, 300), (400, 400), (255, 255, 255), -1)
    result = svc.check_blur(frame)
    assert result["status"] == "ok"
    assert result["metric"] > 50


def test_blur_detection_blurry_frame():
    """Very blurry frame is detected."""
    from edge.camera_health import CameraHealthService
    import cv2
    svc = CameraHealthService(camera_id="cam1")
    frame = np.random.randint(100, 150, (480, 640, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(frame, (51, 51), 30)
    result = svc.check_blur(blurred)
    assert result["status"] == "obscured"
    assert result["metric"] < 50


def test_frozen_detection_different_frames():
    """Different frames are not frozen."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
    result = svc.check_frozen(frame1, frame2)
    assert result["status"] == "ok"
    assert result["metric"] > 1.0


def test_frozen_detection_identical_frames():
    """Identical frames are detected as frozen."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = svc.check_frozen(frame, frame.copy())
    assert result["status"] == "frozen"
    assert result["metric"] < 1.0
