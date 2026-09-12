"""Task 22: Clip overlay renderer tests."""
import numpy as np
import cv2
import os
import tempfile
import pytest

from fusion_server.services.clip_overlay import (
    render_overlay,
    overlay_roi_polygon,
    overlay_text_with_bg,
    _threat_color,
    _severity_label,
)


def _make_test_video(path: str, frames: int = 5, w: int = 320, h: int = 240):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, 25.0, (w, h))
    for i in range(frames):
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        out.write(frame)
    out.release()


def _make_roi():
    return [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]


class TestThreatLabeling:
    def test_severity_label_critical(self):
        assert _severity_label(0.9) == "CRITICAL"

    def test_severity_label_high(self):
        assert _severity_label(0.6) == "HIGH"

    def test_severity_label_medium(self):
        assert _severity_label(0.4) == "MEDIUM"

    def test_severity_label_low(self):
        assert _severity_label(0.1) == "LOW"

    def test_threat_color_varies(self):
        assert _threat_color(0.9) != _threat_color(0.1)


class TestOverlayFunctions:
    def test_overlay_roi_polygon_draws_on_frame(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        original = frame.copy()
        roi = _make_roi()
        result = overlay_roi_polygon(frame, roi)
        assert result.shape == frame.shape
        assert not np.array_equal(result, original)

    def test_overlay_text_with_bg(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        original = frame.copy()
        result = overlay_text_with_bg(frame, "Test", (10, 30))
        assert result.shape == frame.shape
        assert not np.array_equal(result, original)

    def test_overlay_text_empty_string(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        result = overlay_text_with_bg(frame, "", (10, 30))
        assert np.array_equal(result, frame)


class TestRenderOverlay:
    def test_render_overlay_creates_file(self, tmp_path):
        src = str(tmp_path / "src.mp4")
        dst = str(tmp_path / "dst.mp4")
        _make_test_video(src)

        result = render_overlay(
            input_path=src,
            output_path=dst,
            camera_id="cam1",
            timestamp="2026-01-01T00:00:00",
            threat_score=0.9,
            roi_polygon=_make_roi(),
            reason="test breach",
        )
        assert result == dst
        assert os.path.exists(dst)
        assert os.path.getsize(dst) > 0

    def test_render_overlay_no_roi(self, tmp_path):
        src = str(tmp_path / "src.mp4")
        dst = str(tmp_path / "dst.mp4")
        _make_test_video(src)

        result = render_overlay(
            input_path=src,
            output_path=dst,
            camera_id="cam2",
            timestamp="2026-01-01T00:00:00",
            threat_score=0.2,
        )
        assert os.path.exists(result)

    def test_render_overlay_invalid_input_raises(self):
        with pytest.raises(RuntimeError, match="Cannot open video"):
            render_overlay(
                input_path="/nonexistent/video.mp4",
                output_path="/tmp/out.mp4",
                camera_id="cam1",
                timestamp="2026-01-01T00:00:00",
                threat_score=0.5,
            )

    def test_render_overlay_low_score(self, tmp_path):
        src = str(tmp_path / "src.mp4")
        dst = str(tmp_path / "dst.mp4")
        _make_test_video(src, frames=3)

        result = render_overlay(
            input_path=src,
            output_path=dst,
            camera_id="cam3",
            timestamp="2026-01-01T00:00:00",
            threat_score=0.05,
        )
        assert os.path.exists(result)
