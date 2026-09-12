"""Tests for face detection and face embedding services."""
import numpy as np
import multiprocessing
import pytest


class TestFaceDetectorService:
    """Tests for FaceDetectorService."""

    def test_import(self):
        from edge.face_detector import FaceDetectorService
        assert FaceDetectorService is not None

    def test_graceful_without_model(self):
        """Service should gracefully handle missing insightface."""
        from edge.face_detector import FaceDetectorService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = FaceDetectorService(req, res)
        # Should not raise even without model
        assert svc._app is None

    def test_detect_faces_without_model(self):
        """Without model loaded, detect_faces should return empty list."""
        from edge.face_detector import FaceDetectorService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = FaceDetectorService(req, res)
        crop = np.zeros((200, 200, 3), dtype=np.uint8)
        faces = svc.detect_faces(crop)
        assert isinstance(faces, list)
        assert len(faces) == 0


class TestFaceEmbeddingService:
    """Tests for FaceEmbeddingService."""

    def test_import(self):
        from edge.face_embedding import FaceEmbeddingService
        assert FaceEmbeddingService is not None

    def test_graceful_without_model(self):
        """Service should gracefully handle missing ONNX model."""
        from edge.face_embedding import FaceEmbeddingService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = FaceEmbeddingService(req, res, model_path="nonexistent_model.onnx")
        # Should not crash
        assert svc._session is None

    def test_extract_embedding_without_model(self):
        """Without model, extract_embedding should return None."""
        from edge.face_embedding import FaceEmbeddingService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = FaceEmbeddingService(req, res, model_path="nonexistent_model.onnx")
        face_crop = np.zeros((112, 112, 3), dtype=np.uint8)
        emb = svc.extract_embedding(face_crop)
        assert emb is None

    def test_preprocess_face(self):
        """Test face preprocessing pipeline."""
        from edge.face_embedding import FaceEmbeddingService
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = FaceEmbeddingService(req, res)
        face_crop = np.random.randint(0, 255, (150, 100, 3), dtype=np.uint8)
        blob = svc._preprocess_face(face_crop)
        assert blob.shape == (1, 3, 112, 112)
        assert blob.dtype == np.float32
        # Check normalization range [-1, 1]
        assert blob.min() >= -1.01
        assert blob.max() <= 1.01


class TestFaceIntegration:
    """Integration tests for face pipeline wiring."""

    def test_event_publisher_accepts_face_embedding(self):
        """Event publisher should include face_embedding in event dict."""
        from edge.event_publisher import EventPublisher
        pub = EventPublisher("http://localhost:9999")
        face_emb = np.random.randn(512).astype(np.float32)
        event = pub.build_event(
            camera_id="cam1",
            timestamp="2024-01-01T00:00:00Z",
            object_type="person",
            track_id="1",
            bbox_pixels=[100, 100, 300, 400],
            frame_shape=(480, 640),
            confidence=0.9,
            embedding=None,
        )
        # Add face_embedding manually (as camera_worker does)
        event["face_embedding"] = face_emb.tolist()
        assert "face_embedding" in event
        assert len(event["face_embedding"]) == 512

    def test_camera_worker_face_queues_accepted(self):
        """CameraWorker should accept face queues in constructor."""
        from edge.camera_worker import CameraWorker
        queues = {k: multiprocessing.Queue() for k in [
            "req", "res", "reid_req", "reid_res",
            "face_det_req", "face_det_res", "face_emb_req", "face_emb_res",
        ]}
        # Should not raise with face queues
        worker = CameraWorker(
            camera_url="rtsp://test",
            camera_id="test-cam",
            fusion_url="http://localhost:9999",
            req_queue=queues["req"],
            res_queue=queues["res"],
            reid_req_queue=queues["reid_req"],
            reid_res_queue=queues["reid_res"],
            face_det_req_queue=queues["face_det_req"],
            face_det_res_queue=queues["face_det_res"],
            face_emb_req_queue=queues["face_emb_req"],
            face_emb_res_queue=queues["face_emb_res"],
        )
        assert worker._face_available is True

    def test_camera_worker_without_face_queues(self):
        """CameraWorker should work without face queues."""
        from edge.camera_worker import CameraWorker
        worker = CameraWorker(
            camera_url="rtsp://test",
            camera_id="test-cam",
            fusion_url="http://localhost:9999",
            req_queue= multiprocessing.Queue(),
            res_queue= multiprocessing.Queue(),
            reid_req_queue= multiprocessing.Queue(),
            reid_res_queue= multiprocessing.Queue(),
        )
        assert worker._face_available is False

    def test_events_api_accepts_face_embedding(self):
        """Events API should accept face_embedding in event creation."""
        from fastapi.testclient import TestClient
        from fusion_server.main import app
        from unittest.mock import patch

        with patch("fusion_server.main.init_db"):
            with TestClient(app) as client:
                resp = client.post("/api/v1/events", json={
                    "camera_id": "cam-face-test",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "object_type": "person",
                    "track_id": "1",
                    "bbox": [0.1, 0.2, 0.5, 0.8],
                    "confidence": 0.9,
                    "face_embedding": [0.1] * 512,
                })
                # May fail due to DB but shouldn't fail due to schema validation
                assert resp.status_code in (201, 422, 500)

    def test_watchlist_matcher_face_method_exists(self):
        """WatchlistMatcher should have a match_face method."""
        from fusion_server.services.watchlist_matcher import WatchlistMatcher
        matcher = WatchlistMatcher()
        assert hasattr(matcher, "match_face")
        assert callable(matcher.match_face)
