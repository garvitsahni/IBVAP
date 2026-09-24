"""CooldownGate: deterministic alert dedup (no ML) — first fire, 60s cooldown,
per-ROI re-arm on absence, independent keys."""
import pytest

from fusion_server.services.cooldown_gate import CooldownGate, get_cooldown_gate


@pytest.fixture
def gate():
    return CooldownGate()


def test_first_fire_allowed(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True


def test_repeat_within_cooldown_blocked(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1010.0) is False
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1059.0) is False


def test_refires_after_60s_while_still_inside(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1060.0) is True


def test_absence_then_reentry_refires_immediately(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    gate.update_presence("cam1", "obj1", violating_rois=set())  # left every ROI
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1005.0) is True


def test_leaving_one_roi_does_not_rearm_another(gate):
    assert gate.should_fire("cam1", "obj1", "roi:A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj1", "roi:B", violating=True, now=1001.0) is True
    # Still inside B only → A deactivates, B stays active
    gate.update_presence("cam1", "obj1", violating_rois={"B"})
    assert gate.should_fire("cam1", "obj1", "roi:B", violating=True, now=1002.0) is False
    assert gate.should_fire("cam1", "obj1", "roi:A", violating=True, now=1003.0) is True


def test_keys_are_independent_per_object_and_camera(gate):
    assert gate.should_fire("cam1", "obj1", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam1", "obj2", "roi:Zone A", violating=True, now=1000.0) is True
    assert gate.should_fire("cam2", "obj1", "roi:Zone A", violating=True, now=1000.0) is True


def test_watchlist_key_is_time_only_cooldown(gate):
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1000.0) is True
    # update_presence must NOT deactivate non-roi keys
    gate.update_presence("cam1", "obj1", violating_rois=set())
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1030.0) is False
    assert gate.should_fire("cam1", "obj1", "watchlist_match", violating=True, now=1060.0) is True


def test_singleton():
    a = get_cooldown_gate()
    b = get_cooldown_gate()
    assert a is b
    a.reset()
