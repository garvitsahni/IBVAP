"""Tests for CameraWorker Re-ID integration."""
import numpy as np
import multiprocessing
import pytest


def test_camera_worker_crops_detection():
    """CameraWorker correctly crops a detection from the frame."""
    from edge.camera_worker import CameraWorker

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req = multiprocessing.Queue()
    reid_res = multiprocessing.Queue()

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = req_queue
    worker.res_queue = res_queue
    worker.reid_req_queue = reid_req
    worker.reid_res_queue = reid_res

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    assert crop is not None
    assert crop.shape[2] == 3
    assert crop.shape[0] > 0
    assert crop.shape[1] > 0


def test_camera_worker_sends_crop_to_reid():
    """CameraWorker sends crops to ReIDService queue."""
    from edge.camera_worker import CameraWorker

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    reid_req = multiprocessing.Queue()
    reid_res = multiprocessing.Queue()

    worker = CameraWorker.__new__(CameraWorker)
    worker.camera_id = "cam1"
    worker.req_queue = req_queue
    worker.res_queue = res_queue
    worker.reid_req_queue = reid_req
    worker.reid_res_queue = reid_res

    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    detection = {"bbox": [100, 50, 200, 300], "confidence": 0.9, "class_id": 0, "class_name": "person"}

    crop = worker._crop_detection(frame, detection)
    worker.reid_req_queue.put((1, "cam1", crop, "person"))

    assert not worker.reid_req_queue.empty()
    item = worker.reid_req_queue.get_nowait()
    assert item[0] == 1
    assert item[1] == "cam1"
    assert item[3] == "person"
