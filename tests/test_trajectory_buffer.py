"""Tests for trajectory history buffer."""
import time
import threading
import pytest
from fusion_server.core.trajectory_buffer import TrajectoryBuffer
from fusion_server.core.trajectory import TrajectoryPoint


def test_add_single_point():
    """Adding a point stores it correctly."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    pt = TrajectoryPoint(x=0.5, y=0.5, timestamp=1000.0)
    buf.add("obj1", pt)
    history = buf.get_history("obj1")
    assert len(history) == 1
    assert history[0].x == 0.5
    assert history[0].y == 0.5


def test_add_multiple_points_preserves_order():
    """Points are stored in insertion order."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    pts = [
        TrajectoryPoint(x=0.1, y=0.1, timestamp=1.0),
        TrajectoryPoint(x=0.2, y=0.2, timestamp=2.0),
        TrajectoryPoint(x=0.3, y=0.3, timestamp=3.0),
    ]
    for p in pts:
        buf.add("obj1", p)
    history = buf.get_history("obj1")
    assert len(history) == 3
    assert history[0].timestamp == 1.0
    assert history[2].timestamp == 3.0


def test_max_points_per_object():
    """Buffer evicts oldest points when max exceeded."""
    buf = TrajectoryBuffer(max_points_per_object=3)
    for i in range(5):
        buf.add("obj1", TrajectoryPoint(x=float(i), y=float(i), timestamp=float(i)))
    history = buf.get_history("obj1")
    assert len(history) == 3
    assert history[0].x == 2.0
    assert history[2].x == 4.0


def test_separate_objects_independent():
    """Different object_ids have independent histories."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    buf.add("obj1", TrajectoryPoint(x=0.1, y=0.1, timestamp=1.0))
    buf.add("obj2", TrajectoryPoint(x=0.9, y=0.9, timestamp=1.0))
    assert len(buf.get_history("obj1")) == 1
    assert len(buf.get_history("obj2")) == 1


def test_get_history_unknown_object():
    """Unknown object returns empty list."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    assert buf.get_history("nonexistent") == []


def test_get_recent_points():
    """get_recent returns up to N most recent points."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    for i in range(10):
        buf.add("obj1", TrajectoryPoint(x=float(i), y=float(i), timestamp=float(i)))
    recent = buf.get_recent("obj1", n=3)
    assert len(recent) == 3
    assert recent[0].timestamp == 7.0
    assert recent[2].timestamp == 9.0


def test_clear_object():
    """clear removes history for one object."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    buf.add("obj1", TrajectoryPoint(x=0.1, y=0.1, timestamp=1.0))
    buf.add("obj2", TrajectoryPoint(x=0.9, y=0.9, timestamp=1.0))
    buf.clear("obj1")
    assert buf.get_history("obj1") == []
    assert len(buf.get_history("obj2")) == 1


def test_clear_all():
    """clear_all resets entire buffer."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    buf.add("obj1", TrajectoryPoint(x=0.1, y=0.1, timestamp=1.0))
    buf.add("obj2", TrajectoryPoint(x=0.9, y=0.9, timestamp=1.0))
    buf.clear_all()
    assert buf.get_history("obj1") == []
    assert buf.get_history("obj2") == []


def test_object_count():
    """object_count returns number of tracked objects."""
    buf = TrajectoryBuffer(max_points_per_object=100)
    assert buf.object_count() == 0
    buf.add("obj1", TrajectoryPoint(x=0.1, y=0.1, timestamp=1.0))
    buf.add("obj2", TrajectoryPoint(x=0.9, y=0.9, timestamp=1.0))
    assert buf.object_count() == 2
    buf.clear("obj1")
    assert buf.object_count() == 1


def test_thread_safety():
    """Concurrent add/get does not raise."""
    buf = TrajectoryBuffer(max_points_per_object=50)
    errors = []

    def writer(obj_id, n):
        try:
            for i in range(n):
                buf.add(obj_id, TrajectoryPoint(x=float(i), y=float(i), timestamp=float(i)))
        except Exception as e:
            errors.append(e)

    def reader(obj_id):
        try:
            for _ in range(20):
                buf.get_history(obj_id)
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(5):
        threads.append(threading.Thread(target=writer, args=(f"obj{i}", 50)))
        threads.append(threading.Thread(target=reader, args=(f"obj{i}",)))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


def test_default_max_points():
    """Default max_points_per_object is 1000."""
    buf = TrajectoryBuffer()
    for i in range(1001):
        buf.add("obj1", TrajectoryPoint(x=float(i), y=float(i), timestamp=float(i)))
    history = buf.get_history("obj1")
    assert len(history) == 1000
    assert history[0].x == 1.0
