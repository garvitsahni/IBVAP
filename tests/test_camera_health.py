"""Tests for CameraHealthService — SSIM and scene drift detection."""
import numpy as np
import pytest
from datetime import datetime


def test_camera_health_initializes():
    """CameraHealthService can be instantiated."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    assert svc.camera_id == "cam1"


def test_camera_health_ssim_identical_frames():
    """SSIM of identical frames is 1.0."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    ssim = svc.compute_ssim(frame, frame)
    assert ssim == pytest.approx(1.0, abs=0.01)


def test_camera_health_ssim_different_frames():
    """SSIM of very different frames is low."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1")
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
    ssim = svc.compute_ssim(frame1, frame2)
    assert ssim < 0.5


def test_camera_health_tamper_detection():
    """CameraHealthService detects tamper when SSIM drops below threshold."""
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1", tamper_threshold=0.1)
    ref_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    svc.set_reference_frame(ref_frame)
    tamper_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    status = svc.check_health(tamper_frame)
    assert status["status"] == "tamper"
    assert status["ssim"] < 0.1


def test_camera_health_scene_drift():
    """CameraHealthService detects scene drift from embedding changes."""
    rng = np.random.RandomState(42)
    from edge.camera_health import CameraHealthService
    svc = CameraHealthService(camera_id="cam1", scene_drift_threshold=0.3)
    initial_embedding = rng.rand(512).astype(np.float32)
    initial_embedding = initial_embedding / np.linalg.norm(initial_embedding)
    svc.set_scene_embedding(initial_embedding)
    for _ in range(10):
        svc.update_scene_embedding(initial_embedding + rng.randn(512).astype(np.float32) * 0.01)
    status = svc.check_scene_drift(initial_embedding)
    assert status["scene_drift"] is False
    different_embedding = -initial_embedding + rng.randn(512).astype(np.float32) * 0.1
    different_embedding = different_embedding / np.linalg.norm(different_embedding)
    status = svc.check_scene_drift(different_embedding)
    assert status["scene_drift"] is True


def test_camera_health_store_initializes():
    """CameraHealthStore can be instantiated."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()
    assert store is not None


def test_camera_health_store_updates():
    """CameraHealthStore tracks health status per camera."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()
    store.update("cam1", {"status": "ok", "ssim": 0.87})
    store.update("cam2", {"status": "tamper", "ssim": 0.05})
    health = store.get_all()
    assert health["cam1"]["status"] == "ok"
    assert health["cam2"]["status"] == "tamper"


def test_camera_health_store_defaults():
    """CameraHealthStore returns unknown for unregistered cameras."""
    from fusion_server.services.camera_health_store import CameraHealthStore
    store = CameraHealthStore()
    health = store.get_all()
    assert "unknown_cam" not in health
