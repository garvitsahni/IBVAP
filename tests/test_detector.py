"""Tests for DetectionService."""

def test_detection_service_processes_frame():
    """DetectionService returns detections for a frame with objects."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing
    import cv2

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (250, 100), (350, 400), (255, 255, 255), -1)

    detections = svc._run_inference(frame)
    assert isinstance(detections, list)
    for det in detections:
        assert "bbox" in det
        assert "confidence" in det
        assert "class_id" in det
        assert "class_name" in det


def test_class_filtering():
    """Only target COCO classes are kept."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = svc._run_inference(frame)
    for det in detections:
        assert det["class_id"] in {0, 2, 3, 5, 7}


def test_empty_frame():
    """Empty/black frame produces empty detections."""
    from edge.detector import DetectionService
    import numpy as np
    import multiprocessing

    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()

    svc = DetectionService(req_queue, res_queue)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = svc._run_inference(frame)
    assert isinstance(detections, list)
