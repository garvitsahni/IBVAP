"""Verify YOLOv8n loads and produces detections on a synthetic frame."""
import numpy as np

def test_yolov8n_loads():
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    assert model is not None

def test_yolov8n_runs_inference():
    from ultralytics import YOLO
    import cv2
    model = YOLO("yolov8n.pt")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (250, 100), (350, 400), (255, 255, 255), -1)
    results = model(frame, classes=[0, 2, 3, 5, 7], verbose=False)
    assert len(results) > 0
    assert results[0].boxes is not None
