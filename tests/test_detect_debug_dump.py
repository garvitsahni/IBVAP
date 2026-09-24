"""Debug capture for car-miss diagnosis: flag-gated, capped, never raises."""
import json
import os

import cv2
import numpy as np

from fusion_server.api.routes import detect as detect_mod
from fusion_server.api.routes.detect import (
    BBoxResponse,
    DetectionResult,
    _maybe_debug_dump,
)


def _frame():
    return np.zeros((120, 160, 3), dtype=np.uint8)


def _det(cid=2, conf=0.5, name="car"):
    return DetectionResult(
        bbox=BBoxResponse(x1=10, y1=10, x2=100, y2=100),
        confidence=conf, class_name=name, class_id=cid,
    )


def test_dump_off_by_default_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("IBVAP_DEBUG_DETECT", raising=False)
    monkeypatch.setenv("IBVAP_DEBUG_DIR", str(tmp_path))
    _maybe_debug_dump(_frame(), [_det()], [_det()], {"passes": 1})
    assert list(tmp_path.iterdir()) == []


def test_dump_on_writes_jpg_and_json(tmp_path, monkeypatch):
    monkeypatch.setenv("IBVAP_DEBUG_DETECT", "1")
    monkeypatch.setenv("IBVAP_DEBUG_DIR", str(tmp_path))
    monkeypatch.setattr(detect_mod, "_debug_dump_count", 0)
    raw = [_det(conf=0.9 - i * 0.01) for i in range(60)]
    _maybe_debug_dump(_frame(), raw, [_det()], {"passes": 2, "brightness": 120.0})
    jpgs = list(tmp_path.glob("*.jpg"))
    payloads = list(tmp_path.glob("*.json"))
    assert len(jpgs) == 1 and len(payloads) == 1
    img = cv2.imread(str(jpgs[0]))
    assert img is not None and img.shape[:2] == (120, 160)
    data = json.loads(payloads[0].read_text())
    assert data["meta"] == {"passes": 2, "brightness": 120.0}
    assert len(data["raw_predictions"]) == 50  # capped, conf-sorted
    assert data["raw_predictions"][0]["confidence"] == 0.9
    assert data["raw_predictions"][0]["class_name"] == "car"
    assert len(data["final_detections"]) == 1


def test_dump_respects_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("IBVAP_DEBUG_DETECT", "1")
    monkeypatch.setenv("IBVAP_DEBUG_DIR", str(tmp_path))
    monkeypatch.setenv("IBVAP_DEBUG_MAX_FRAMES", "2")
    monkeypatch.setattr(detect_mod, "_debug_dump_count", 0)
    for _ in range(4):
        _maybe_debug_dump(_frame(), [], [], {})
    assert len(list(tmp_path.glob("*.jpg"))) == 2


def test_dump_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("IBVAP_DEBUG_DETECT", "1")
    # Point the "dir" at an existing file so makedirs/imwrite cannot succeed
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setenv("IBVAP_DEBUG_DIR", str(blocker))
    monkeypatch.setattr(detect_mod, "_debug_dump_count", 0)
    _maybe_debug_dump(_frame(), [_det()], [_det()], {})  # must not raise
    _maybe_debug_dump(None, [], [], {})  # garbage input must not raise either
