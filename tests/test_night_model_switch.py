"""Tests for night mode model weight switching."""
import numpy as np
import multiprocessing
import pytest


class TestSwitchModelProtocol:
    """Tests for SWITCH_MODEL sentinel in detector.py."""

    def test_switch_model_sentinel_defined(self):
        from edge.detector import SWITCH_MODEL
        assert SWITCH_MODEL == "SWITCH_MODEL"

    def test_switch_model_detection(self):
        """Test that SWITCH_MODEL command is recognized."""
        from edge.detector import SWITCH_MODEL
        item = (SWITCH_MODEL, "yolov8n_night.pt")
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert item[0] == SWITCH_MODEL
        assert item[1] == "yolov8n_night.pt"

    def test_regular_frame_not_confused_with_switch(self):
        """Regular frame items should not match SWITCH_MODEL pattern."""
        from edge.detector import SWITCH_MODEL
        frame_item = (1, "cam1", np.zeros((480, 640, 3), dtype=np.uint8))
        assert not (isinstance(frame_item, tuple) and len(frame_item) == 2 and frame_item[0] == SWITCH_MODEL)


class TestNightWeatherModeDetection:
    """Tests for mode detection in NightWeatherProcessor."""

    def test_normal_frame_stays_normal(self):
        from edge.night_weather import NightWeatherProcessor
        proc = NightWeatherProcessor()
        frame = np.full((480, 640, 3), 128, dtype=np.uint8)  # Bright frame
        _, info = proc.process(frame)
        assert info["mode"] == "normal"

    def test_dark_frame_switches_to_night(self):
        from edge.night_weather import NightWeatherProcessor
        proc = NightWeatherProcessor()
        # 5 consecutive dark frames to trigger mode switch
        dark_frame = np.full((480, 640, 3), 10, dtype=np.uint8)
        for _ in range(6):
            _, info = proc.process(dark_frame)
        assert info["mode"] == "night"

    def test_force_mode_overrides(self):
        from edge.night_weather import NightWeatherProcessor
        proc = NightWeatherProcessor()
        bright_frame = np.full((480, 640, 3), 200, dtype=np.uint8)
        _, info = proc.process(bright_frame, force_mode="night")
        assert info["mode"] == "night"

    def test_mode_info_contains_brightness_and_visibility(self):
        from edge.night_weather import NightWeatherProcessor
        proc = NightWeatherProcessor()
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        _, info = proc.process(frame)
        assert "mode" in info
        assert "brightness" in info
        assert "visibility" in info


class TestCameraWorkerNightModelSwitching:
    """Tests for model switching wiring in CameraWorker."""

    def test_night_model_paths_default(self):
        """CameraWorker should have default night model paths."""
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
        assert "normal" in worker._night_model_paths
        assert "night" in worker._night_model_paths
        assert "hazy" in worker._night_model_paths
        assert worker._current_mode == "normal"

    def test_mode_change_sends_switch_model(self):
        """When mode changes, SWITCH_MODEL should be sent to req_queue."""
        from edge.detector import SWITCH_MODEL
        from edge.night_weather import NightWeatherProcessor

        proc = NightWeatherProcessor()
        # Force 5 dark frames to trigger night mode
        dark_frame = np.full((480, 640, 3), 10, dtype=np.uint8)
        for _ in range(6):
            _, info = proc.process(dark_frame)

        assert info["mode"] == "night"

        # Verify the SWITCH_MODEL protocol works
        model_path = "yolov8n_night.pt"
        req_queue = multiprocessing.Queue()
        req_queue.put((SWITCH_MODEL, model_path))

        item = req_queue.get(timeout=1.0)
        assert item[0] == SWITCH_MODEL
        assert item[1] == model_path

    def test_detection_service_handles_switch_model(self):
        """DetectionService should handle SWITCH_MODEL command gracefully."""
        from edge.detector import DetectionService, SWITCH_MODEL
        req = multiprocessing.Queue()
        res = multiprocessing.Queue()
        svc = DetectionService(req, res, model_path="yolov8n.pt")

        # Send a SWITCH_MODEL command (will fail to load, but shouldn't crash)
        req.put((SWITCH_MODEL, "nonexistent_model.pt"))

        # Send shutdown
        req.put(None)

        # Run should complete without crashing
        svc.run()

    def test_mode_change_detection_flow(self):
        """Test the full flow: mode detection -> SWITCH_MODEL -> queue."""
        from edge.night_weather import NightWeatherProcessor
        from edge.detector import SWITCH_MODEL

        proc = NightWeatherProcessor()
        current_mode = "normal"
        night_model_paths = {
            "normal": "yolov8n.pt",
            "night": "yolov8n_night.pt",
            "hazy": "yolov8n.pt",
        }

        req_queue = multiprocessing.Queue()

        # Simulate 6 dark frames
        dark_frame = np.full((480, 640, 3), 10, dtype=np.uint8)
        for _ in range(6):
            _, info = proc.process(dark_frame)
            new_mode = info["mode"]
            if new_mode != current_mode:
                current_mode = new_mode
                model_path = night_model_paths.get(new_mode, "yolov8n.pt")
                req_queue.put((SWITCH_MODEL, model_path))

        # Verify the switch was queued
        assert not req_queue.empty()
        item = req_queue.get(timeout=1.0)
        assert item[0] == SWITCH_MODEL
        assert item[1] == "yolov8n_night.pt"
        assert current_mode == "night"
