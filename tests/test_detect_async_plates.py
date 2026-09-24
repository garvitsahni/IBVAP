"""Async plate split: fast detection path never runs OCR; background job does."""
import numpy as np
import pytest

from fusion_server.api.routes import detect as detect_mod
from fusion_server.api.routes.detect import (
    BBoxResponse,
    DetectionResult,
    _plate_ocr_job,
    _process_frame,
    _read_plates_for_dets,
)


def _frame():
    return np.zeros((120, 160, 3), dtype=np.uint8)


def _vehicle(conf=0.8):
    return DetectionResult(
        bbox=BBoxResponse(x1=10, y1=10, x2=100, y2=100),
        confidence=conf, class_name="car", class_id=2,
    )


def test_fast_path_never_runs_ocr(monkeypatch):
    def _explode(*a, **k):
        raise AssertionError("OCR must not run on the fast path")
    monkeypatch.setattr(detect_mod, "_read_plate", _explode)
    monkeypatch.setattr(detect_mod, "_get_plate_detector", lambda: None)
    out = _process_frame(_frame(), 0.10, "test-cam", run_plates=False)
    assert out["plate_reads"] == []
    assert all(d.plate_text is None for d in out["detections"])


def test_helper_reads_vehicle_plates(monkeypatch):
    monkeypatch.setattr(detect_mod, "_read_plate", lambda *a, **k: "MH12AB1234")
    monkeypatch.setattr(detect_mod, "_get_plate_detector", lambda: None)
    dets = [_vehicle(), DetectionResult(
        bbox=BBoxResponse(x1=1, y1=1, x2=5, y2=5),
        confidence=0.9, class_name="person", class_id=0)]
    res = _read_plates_for_dets(_frame(), dets, "cam1")
    assert dets[0].plate_text == "MH12AB1234"
    assert dets[1].plate_text is None
    assert res["plate_reads"] == [{
        "camera_id": "cam1", "plate_text": "MH12AB1234",
        "class_name": "car", "confidence": 0.8}]


def test_helper_never_raises(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("ocr exploded")
    monkeypatch.setattr(detect_mod, "_read_plate", _boom)
    monkeypatch.setattr(detect_mod, "_get_plate_detector", _boom)
    res = _read_plates_for_dets(_frame(), [_vehicle()], "cam1")
    assert res["plate_reads"] == []
    assert res["detections"][0].plate_text is None


async def test_plate_job_broadcasts_and_releases(monkeypatch):
    monkeypatch.setattr(detect_mod, "_read_plate", lambda *a, **k: "KA05MN6789")
    sent = []

    class FakeBroadcaster:
        async def broadcast_plate_read(self, event):
            sent.append(event)

    # _plate_ocr_job does "from ...broadcaster import get_broadcaster" inside
    # itself, so patch the source module attribute.
    import fusion_server.services.broadcaster as bc
    monkeypatch.setattr(bc, "get_broadcaster", lambda: FakeBroadcaster())
    detect_mod._ocr_busy.clear()
    await _plate_ocr_job(_frame(), [_vehicle()], "cam9")
    assert sent and sent[0]["plate_text"] == "KA05MN6789"
    assert sent[0]["camera_id"] == "cam9"
    assert not detect_mod._ocr_busy.is_set()


async def test_plate_job_skips_when_busy(monkeypatch):
    def _explode(*a, **k):
        raise AssertionError("must not run while busy")
    monkeypatch.setattr(detect_mod, "_read_plate", _explode)
    detect_mod._ocr_busy.set()
    try:
        await _plate_ocr_job(_frame(), [_vehicle()], "cam9")
    finally:
        detect_mod._ocr_busy.clear()
