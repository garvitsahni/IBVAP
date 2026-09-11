"""
Trajectory History Buffer - Phase 4
In-memory buffer accumulating position history per tracked object.
Thread-safe, configurable max points per object.
"""
from collections import defaultdict, deque
from typing import List
from threading import Lock

from fusion_server.core.trajectory import TrajectoryPoint


class TrajectoryBuffer:
    """
    Stores recent TrajectoryPoint history per object_id.
    Thread-safe via per-object locks and a global lock for structural changes.
    """

    def __init__(self, max_points_per_object: int = 1000):
        self._max_points = max_points_per_object
        self._buffers: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self._max_points)
        )
        self._lock = Lock()

    def add(self, object_id: str, point: TrajectoryPoint) -> None:
        """Append a point to the object's history. Evicts oldest if at capacity."""
        with self._lock:
            self._buffers[object_id].append(point)

    def get_history(self, object_id: str) -> List[TrajectoryPoint]:
        """Return full history for an object (oldest first)."""
        with self._lock:
            return list(self._buffers.get(object_id, []))

    def get_recent(self, object_id: str, n: int = 10) -> List[TrajectoryPoint]:
        """Return the N most recent points (newest last)."""
        with self._lock:
            buf = self._buffers.get(object_id, deque())
            return list(buf)[-n:]

    def clear(self, object_id: str) -> None:
        """Remove all history for one object."""
        with self._lock:
            self._buffers.pop(object_id, None)

    def clear_all(self) -> None:
        """Remove all history for all objects."""
        with self._lock:
            self._buffers.clear()

    def object_count(self) -> int:
        """Number of tracked objects with history."""
        with self._lock:
            return len(self._buffers)
