"""Unit tests for the camera detection latency guard (reduced_accuracy_mode).

SPEC: edge/camera_worker.py — p95 of the last 100 detect round-trip times is
compared against DETECT_LATENCY_BUDGET_MS (default 100ms). After 3 consecutive
breaching evaluations, reduced_accuracy_mode flips to True; when p95 recovers
it flips back to False. Both transitions must be logged.
"""
import pytest
from unittest.mock import MagicMock

from edge.camera_worker import CameraWorker


def _make_worker(budget_ms: float = 100.0) -> CameraWorker:
    # CameraWorker.__init__ builds full pipeline objects; build a bare instance
    # and attach only what the latency guard touches.
    w = object.__new__(CameraWorker)
    w.camera_id = "cam-test"
    w._detect_budget_ms = budget_ms
    from collections import deque
    w._detect_latencies_ms = deque(maxlen=100)
    w._over_budget_streak = 0
    w.reduced_accuracy_mode = False
    return w


def test_warmup_window_does_not_flip():
    """First 9 samples (below warm-up of 10) must never flip the flag."""
    w = _make_worker()
    for _ in range(9):
        w._update_latency_guard(500.0)
    assert w.reduced_accuracy_mode is False
    assert w._over_budget_streak == 0


def test_persistent_breach_raises_flag_after_3_streak():
    """Sustained p95 > budget for 3 evaluations -> flag True."""
    w = _make_worker(budget_ms=100.0)
    # 10 fast samples to pass warm-up, p95 = ~fast value
    for _ in range(10):
        w._update_latency_guard(50.0)
    assert w.reduced_accuracy_mode is False
    # Now every evaluation breaches: p95 of a window containing slow samples
    # climbs above 100ms within a few updates.
    for _ in range(60):
        w._update_latency_guard(250.0)
    assert w.reduced_accuracy_mode is True


def test_recovery_clears_flag():
    """When p95 returns under budget, the flag must clear."""
    w = _make_worker(budget_ms=100.0)
    for _ in range(10):
        w._update_latency_guard(50.0)
    for _ in range(60):
        w._update_latency_guard(250.0)
    assert w.reduced_accuracy_mode is True
    # Sustained fast responses flush the 100-sample ring back under budget
    for _ in range(120):
        w._update_latency_guard(30.0)
    assert w.reduced_accuracy_mode is False
    assert w._over_budget_streak == 0


def test_p95_computation_matches_sorted_index():
    """detect_p95_ms must equal the nearest-rank p95 of the recorded window."""
    w = _make_worker(budget_ms=1000.0)
    for v in range(10, 110):  # 100 samples: 10..109 ms
        w._update_latency_guard(float(v))
    expected = sorted(range(10, 110))
    idx = int(0.95 * (len(expected) - 1))
    assert w.detect_p95_ms() == pytest.approx(expected[idx], abs=0.1)


def test_p95_none_during_warmup():
    """detect_p95_ms returns None until the warm-up window fills."""
    w = _make_worker()
    w._update_latency_guard(80.0)
    assert w.detect_p95_ms() is None


def test_timeout_sample_of_500_always_breaches_default_budget():
    """A 500ms timeout sample must count toward the breach streak (default budget)."""
    w = _make_worker(budget_ms=100.0)
    for _ in range(9):
        w._update_latency_guard(50.0)
    w._update_latency_guard(500.0)  # 10th sample = warm-up complete + breach
    # Window is now mostly fast with one 500ms; nearest-rank p95 lands on a
    # fast value at exactly 10 samples, so streak begins on subsequent updates.
    for _ in range(20):
        w._update_latency_guard(500.0)
    assert w.reduced_accuracy_mode is True
