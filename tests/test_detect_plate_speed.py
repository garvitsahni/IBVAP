"""Webcam /detect plate-path regressions — user report 2026-09-23:

"too slow to recognize anything; box lingers after leaving frame;
plate not read; not working in darkness"

Measured root cause (Phase 1, measure_detect.py):
  _read_plate on ONE synthetic vehicle = 236s  (up to 12 EasyOCR readtext
  calls over 4x-upscaled vehicle-sized regions, no early exit, no width cap).
  Dark frames multiply YOLO passes x4, EACH re-running plate OCR
  => multi-minute requests => single-flight 429s => overlay never refreshes.

These tests pin the contract: plate OCR must early-exit, run ONCE per unique
vehicle per request (after dedup, not per YOLO pass), and YOLO input must
match the 640px upload (1280 wastes 4x CPU).
"""
import time
import numpy as np
import cv2
import pytest

from fusion_server.api.routes import detect


def _synthetic_vehicle_plate_frame():
    """Real rendered plate text inside a vehicle-shaped box (real OCR input)."""
    frame = np.full((720, 1280, 3), 170, np.uint8)
    cv2.rectangle(frame, (300, 250), (980, 620), (50, 50, 160), -1)
    cv2.rectangle(frame, (560, 500), (760, 570), (240, 240, 240), -1)
    cv2.putText(frame, "DL01AB1234", (568, 555), cv2.FONT_HERSHEY_SIMPLEX,
                1.5, (0, 0, 0), 3, cv2.LINE_AA)
    return frame


class _CountingOCR:
    """Delegates to the real EasyOCR reader while counting readtext calls."""

    def __init__(self, real):
        self._real = real
        self.calls = 0

    def readtext(self, img, **kwargs):
        self.calls += 1
        return self._real.readtext(img, **kwargs)


@pytest.fixture()
def counting_ocr(monkeypatch):
    real = detect._get_ocr()
    assert real is not None, "EasyOCR must be installed for these tests"
    counter = _CountingOCR(real)
    monkeypatch.setattr(detect, "_ocr_reader", counter)
    return counter


def test_read_plate_early_exits_within_time_budget(counting_ocr):
    """One vehicle must not cost minutes: bounded readtext calls, <15s wall."""
    frame = _synthetic_vehicle_plate_frame()
    counting_ocr.calls = 0
    t0 = time.time()
    text = detect._read_plate(frame, 300, 250, 980, 620)
    elapsed = time.time() - t0

    assert text is not None, "_read_plate failed to read a clearly rendered plate"
    assert len(text) >= 6, f"implausible plate text: {text!r}"
    assert elapsed < 15, f"_read_plate took {elapsed:.1f}s (root cause: unbounded OCR)"
    assert counting_ocr.calls <= 4, (
        f"readtext called {counting_ocr.calls}x — must early-exit (<=4)"
    )


class _FakeBox:
    def __init__(self, x1, y1, x2, y2, cls=2, conf=0.9):
        self.cls = [np.array([cls])]
        self.conf = [np.array([conf])]
        self.xyxy = [np.array([float(x1), float(y1), float(x2), float(y2)], dtype=float)]


class _FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


def _fake_model_factory(boxes_per_call):
    class _FakeModel:
        last_imgsz = None

        def __call__(self, frame, classes=None, verbose=False, imgsz=None):
            type(self).last_imgsz = imgsz
            return [_FakeResult(list(boxes_per_call()))]

    return _FakeModel()


def test_dark_multipass_runs_plate_ocr_once(monkeypatch):
    """Dark frames run 4 YOLO passes — plate OCR must run once per unique
    vehicle (after dedup), not once per pass (old: 4x ~4min = unusable dark)."""
    vehicle_box = lambda: [_FakeBox(100, 150, 500, 400)]
    fake = _fake_model_factory(vehicle_box)
    monkeypatch.setattr(detect, "_model", fake)

    ocr_calls = []
    # Stub the OCR body — this test counts CALLS; real-OCR behavior is test 1.
    monkeypatch.setattr(detect, "_read_plate", lambda *a, **k: ocr_calls.append(1))

    dark = np.full((480, 640, 3), 30, np.uint8)
    result = detect._process_frame(dark, 0.10, "test")

    vehicle_dets = [d for d in result["detections"] if d.class_name == "car"]
    assert vehicle_dets, "fake YOLO box should survive dedup as a car detection"
    assert len(ocr_calls) <= len(vehicle_dets), (
        f"plate OCR ran {len(ocr_calls)}x for {len(vehicle_dets)} unique vehicle(s) "
        f"across {result['passes']} dark passes — must run once per vehicle"
    )


def test_yolo_input_matches_upload_size(monkeypatch):
    """Webcam uploads are 640px wide; imgsz=1280 upscales x2 for no detail gain."""
    fake = _fake_model_factory(lambda: [])
    monkeypatch.setattr(detect, "_model", fake)
    detect._run_yolo(np.zeros((480, 640, 3), np.uint8), 0.1)
    assert fake.last_imgsz == 640, f"imgsz={fake.last_imgsz}, expected 640"
