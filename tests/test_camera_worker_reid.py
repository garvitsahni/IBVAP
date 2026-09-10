"""Tests for CameraWorker Re-ID integration."""
import numpy as np
import queue
import pytest


def test_camera_worker_crops_detection():
    """CameraWorker correctly crops a detection from the frame."""
    from edge.camera_worker import CameraWorker

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = queue.Queue()
    worker.res_queue = queue.Queue()
    worker.reid_req_queue = queue.Queue()
    worker.reid_res_queue = queue.Queue()

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    assert crop is not None
    assert crop.shape == (250, 100, 3)


def test_camera_worker_sends_crop_to_reid():
    """CameraWorker sends crops to ReIDService queue with track_id."""
    from edge.camera_worker import CameraWorker

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = queue.Queue()
    worker.res_queue = queue.Queue()
    worker.reid_req_queue = queue.Queue()
    worker.reid_res_queue = queue.Queue()

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    worker.reid_req_queue.put((1, "cam1", 42, crop, "person"))

    assert not worker.reid_req_queue.empty()
    item = worker.reid_req_queue.get_nowait()
    assert item[0] == 1
    assert item[1] == "cam1"
    assert item[2] == 42
    assert item[4] == "person"
