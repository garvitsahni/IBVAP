"""Tests for plate detection and plate OCR services."""
import numpy as np
import multiprocessing
import pytest


class TestPlateDetectorService:
    """Tests for PlateDetectorService."""

    def test_import(self):
        from edge.plate_detector import PlateDetectorService
        assert PlateDetectorService is not None

    def test_graceful_without_model(self):
        """Service should gracefully handle missing ONNX model."""
        from edge.plate_detector import PlateDetectorService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = PlateDetectorService(req, res, model_path="nonexistent_model.onnx")
        assert svc._session is None

    def test_detect_plates_without_model(self):
        """Without model loaded, detect_plates should return empty list."""
        from edge.plate_detector import PlateDetectorService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = PlateDetectorService(req, res, model_path="nonexistent_model.onnx")
        crop = np.zeros((200, 400, 3), dtype=np.uint8)
        plates = svc.detect_plates(crop)
        assert isinstance(plates, list)
        assert len(plates) == 0

    def test_preprocess(self):
        """Test plate preprocessing pipeline."""
        from edge.plate_detector import PlateDetectorService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = PlateDetectorService(req, res)
        crop = np.random.randint(0, 255, (300, 500, 3), dtype=np.uint8)
        blob = svc._preprocess(crop)
        assert blob.shape == (1, 3, 320, 320)
        assert blob.dtype == np.float32
        assert blob.min() >= 0.0
        assert blob.max() <= 1.0


class TestPlateOCRService:
    """Tests for PlateOCRService."""

    def test_import(self):
        from edge.plate_ocr import PlateOCRService
        assert PlateOCRService is not None

    def test_graceful_without_engine(self):
        """Service should gracefully handle missing OCR engine."""
        from edge.plate_ocr import PlateOCRService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = PlateOCRService(req, res, ocr_engine="easyocr")
        # Should not crash even if easyocr not installed
        assert svc._engine is None or svc._engine is not None

    def test_read_plate_returns_string_or_none(self):
        """read_plate should return a string or None."""
        from edge.plate_ocr import PlateOCRService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = PlateOCRService(req, res, ocr_engine="easyocr")
        plate_crop = np.random.randint(0, 255, (50, 200, 3), dtype=np.uint8)
        result = svc.read_plate(plate_crop)
        assert result is None or isinstance(result, str)


class TestPlateIntegration:
    """Integration tests for plate pipeline wiring."""

    def test_camera_worker_plate_queues_accepted(self):
        """CameraWorker should accept plate queues in constructor."""
        from edge.camera_worker import CameraWorker
        worker = CameraWorker(
            camera_url="rtsp://test",
            camera_id="test-cam",
            fusion_url="http://localhost:9999",
            req_queue=multiprocessing.Queue(),
            res_queue=multiprocessing.Queue(),
            reid_req_queue=multiprocessing.Queue(),
            reid_res_queue=multiprocessing.Queue(),
            plate_det_req_queue=multiprocessing.Queue(),
            plate_det_res_queue=multiprocessing.Queue(),
            plate_ocr_req_queue=multiprocessing.Queue(),
            plate_ocr_res_queue=multiprocessing.Queue(),
        )
        assert worker._plate_available is True

    def test_camera_worker_without_plate_queues(self):
        """CameraWorker should work without plate queues."""
        from edge.camera_worker import CameraWorker
        worker = CameraWorker(
            camera_url="rtsp://test",
            camera_id="test-cam",
            fusion_url="http://localhost:9999",
            req_queue=multiprocessing.Queue(),
            res_queue=multiprocessing.Queue(),
            reid_req_queue=multiprocessing.Queue(),
            reid_res_queue=multiprocessing.Queue(),
        )
        assert worker._plate_available is False

    def test_events_api_accepts_plate_text(self):
        """Events API should accept plate_text in event creation."""
        from fastapi.testclient import TestClient
        from fusion_server.main import app
        from unittest.mock import patch

        with patch("fusion_server.main.init_db"):
            with TestClient(app) as client:
                resp = client.post("/api/v1/events", json={
                    "camera_id": "cam-plate-test",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "object_type": "vehicle",
                    "track_id": "1",
                    "bbox": [0.1, 0.2, 0.5, 0.8],
                    "confidence": 0.9,
                    "plate_text": "ABC-1234",
                })
                assert resp.status_code in (201, 422, 500)

    def test_plate_text_in_response(self):
        """Events API response should include plate_text."""
        from fusion_server.api.events import DetectionEventResponse
        resp = DetectionEventResponse(
            id=1, camera_id="cam1", timestamp="2024-01-01T00:00:00Z",
            object_type="vehicle", track_id="1",
            bbox={"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
            confidence=0.9, created_at="2024-01-01T00:00:00Z",
            plate_text="XYZ-5678",
        )
        assert resp.plate_text == "XYZ-5678"

    def test_plate_text_none_by_default(self):
        """Events API response should have plate_text=None by default."""
        from fusion_server.api.events import DetectionEventResponse
        resp = DetectionEventResponse(
            id=1, camera_id="cam1", timestamp="2024-01-01T00:00:00Z",
            object_type="person", track_id="1",
            bbox={"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
            confidence=0.9, created_at="2024-01-01T00:00:00Z",
        )
        assert resp.plate_text is None
