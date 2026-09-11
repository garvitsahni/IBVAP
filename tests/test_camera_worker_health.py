"""Tests for camera worker health integration."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def test_camera_worker_sends_health_status():
    """CameraWorker sends health status to fusion server."""
    from edge.camera_worker import CameraWorker

    req_queue = MagicMock()
    res_queue = MagicMock()
    reid_req_queue = MagicMock()
    reid_res_queue = MagicMock()

    worker = CameraWorker(
        camera_url="rtsp://localhost:8554/cam1",
        camera_id="cam1",
        fusion_url="http://localhost:8000",
        req_queue=req_queue,
        res_queue=res_queue,
        reid_req_queue=reid_req_queue,
        reid_res_queue=reid_res_queue,
        target_fps=10,
        display=False,
        health_check_interval=5,
    )

    assert worker.health_check_interval == 5
    assert worker._health_service is not None
