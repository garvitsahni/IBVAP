"""Tests for ReIDService — Re-ID embedding extraction."""
import numpy as np
import multiprocessing
import pytest


def test_reid_service_initializes():
    """ReIDService can be instantiated with a model path."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")
    assert svc is not None


def test_reid_service_crop_preprocessing():
    """ReIDService preprocesses crop correctly (resize to 256x128, normalize)."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    # Create a fake crop (RGB, any size)
    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    processed = svc._preprocess_crop(crop)
    assert processed.shape == (1, 3, 256, 128)  # NCHW format
    assert processed.dtype == np.float32
    # Should be normalized to [0, 1]
    assert processed.min() >= 0.0
    assert processed.max() <= 1.0


def test_reid_service_returns_embedding():
    """ReIDService returns 512-dim embedding (or None if model unavailable)."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop)
    # With no model loaded, should return None (graceful fallback)
    assert embedding is None


def test_reid_service_queue_protocol():
    """ReIDService processes queue items correctly."""
    import queue
    from edge.reid_service import ReIDService
    req_queue = queue.Queue()
    res_queue = queue.Queue()
    svc = ReIDService(req_queue, res_queue, model_path="nonexistent.onnx")

    # Put a request: (frame_id, camera_id, track_id, crop, object_type)
    crop = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    req_queue.put((1, "cam1", 42, crop, "person"))

    # Process one item
    svc._process_one()

    # Check response
    assert not res_queue.empty()
    fid, cid, tid, embedding, obj_type = res_queue.get_nowait()
    assert fid == 1
    assert cid == "cam1"
    assert tid == 42
    assert obj_type == "person"
    # Embedding is None (no model), but protocol works
    assert embedding is None


def test_reid_service_vehicle_model():
    """ReIDService handles vehicle crops with separate model path."""
    from edge.reid_service import ReIDService
    req_queue = multiprocessing.Queue()
    res_queue = multiprocessing.Queue()
    svc = ReIDService(
        req_queue, res_queue,
        model_path="models/osnet_ain_x1_0.onnx",
        vehicle_model_path="models/vehicle_reid.onnx",
    )
    crop = np.random.randint(0, 255, (80, 200, 3), dtype=np.uint8)
    embedding = svc.extract_embedding(crop, is_vehicle=True)
    # With no vehicle model loaded, should return None
    assert embedding is None


def test_vehicle_preprocess_and_real_inference():
    """Regression: vehicle preprocess must transpose to CHW BEFORE ImageNet
    mean/std normalization. An HWC/(3,1,1) broadcast error made every vehicle
    embedding fail (caught by scripts/bench_link_rate.py). Loads the real
    models/vehicle_reid.onnx."""
    from edge.reid_service import ReIDService
    svc = ReIDService(multiprocessing.Queue(), multiprocessing.Queue())
    crop = np.random.randint(0, 255, (80, 200, 3), dtype=np.uint8)

    blob = svc._preprocess_crop(crop, 256, 256, is_vehicle=True)
    assert blob.shape == (1, 3, 256, 256)
    assert blob.dtype == np.float32

    svc._load_vehicle_model()
    assert svc._vehicle_session is not None, "vehicle_reid.onnx failed to load"
    emb = svc.extract_embedding(crop, is_vehicle=True)
    assert emb is not None, "vehicle embedding failed (preprocess/inference)"
    assert emb.shape == (512,)
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-3
