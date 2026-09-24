"""Edge snapshot: base64 JPEG ≤640px long edge, throttled ≤1/camera/sec,
field absent on failure (never raises — publish path must not break)."""
import base64

import numpy as np

from edge.event_publisher import SnapshotThrottle, encode_snapshot


def _frame(h=480, w=640):
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_encode_returns_base64_jpeg():
    out = encode_snapshot(_frame())
    assert out is not None
    raw = base64.b64decode(out)
    assert raw[:2] == b"\xff\xd8"


def test_encode_downscales_large_frame():
    out = encode_snapshot(_frame(h=1080, w=1920))
    assert out is not None
    # Decode via cv2 to verify long edge <= 640
    import cv2
    img = cv2.imdecode(np.frombuffer(base64.b64decode(out), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    assert max(img.shape[:2]) <= 640


def test_encode_never_raises_on_bad_input():
    assert encode_snapshot(None) is None
    assert encode_snapshot(np.zeros((10, 10), dtype=np.uint8)) is None  # not BGR


def test_throttle_first_call_true_then_false():
    t = SnapshotThrottle(interval=1.0)
    assert t.should_attach(now=100.0) is True
    assert t.should_attach(now=100.5) is False
    assert t.should_attach(now=101.0) is True
