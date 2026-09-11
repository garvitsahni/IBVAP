"""Suspicious activity detection — loitering, path reversal, group clustering."""
import math
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from shapely.geometry import Point, Polygon


@dataclass
class SuspiciousActivity:
    """A detected suspicious activity."""
    activity_type: str  # "loitering" | "path_reversal" | "group_clustering"
    object_id: str
    camera_id: str
    timestamp: float
    duration_s: float = 0.0
    details: str = ""


class SuspiciousActivityDetector:
    """Detects suspicious activity from trajectory data."""

    def __init__(
        self,
        loiter_threshold_s: float = 30.0,
        reversal_angle_deg: float = 90.0,
        reversal_window_s: float = 5.0,
        cluster_min_count: int = 3,
        cluster_radius: float = 0.1,
        cluster_threshold_s: float = 10.0,
    ):
        self._loiter_threshold = loiter_threshold_s
        self._reversal_angle = reversal_angle_deg
        self._reversal_window = reversal_window_s
        self._cluster_min = cluster_min_count
        self._cluster_radius = cluster_radius
        self._cluster_threshold = cluster_threshold_s

        # Per-object state
        self._positions: Dict[str, List[Tuple[float, float, float, str]]] = defaultdict(list)
        self._roi_entry: Dict[str, Dict[str, float]] = {}  # (object_id, roi_key) -> entry_time

    def update(self, object_id: str, camera_id: str, x: float, y: float, timestamp: float) -> None:
        """Record a position update for an object."""
        self._positions[object_id].append((x, y, timestamp, camera_id))
        if len(self._positions[object_id]) > 100:
            self._positions[object_id] = self._positions[object_id][-100:]

    def remove(self, object_id: str) -> None:
        """Remove state for an object."""
        self._positions.pop(object_id, None)
        keys_to_remove = [k for k in self._roi_entry if k.startswith(object_id)]
        for k in keys_to_remove:
            del self._roi_entry[k]

    def check_loitering(self, object_id: str, roi_polygon: List[List[float]]) -> List[SuspiciousActivity]:
        """Check if object has been inside ROI longer than threshold."""
        positions = self._positions.get(object_id, [])
        if not positions:
            return []

        polygon = Polygon(roi_polygon)
        violations = []
        now = positions[-1][2]

        for x, y, ts, cam in reversed(positions):
            point = Point(x, y)
            if not polygon.contains(point):
                break
            # Object is inside — check dwell time
            oldest_inside_ts = ts
            dwell = now - oldest_inside_ts
            if dwell >= self._loiter_threshold:
                violations.append(SuspiciousActivity(
                    activity_type="loitering",
                    object_id=object_id,
                    camera_id=cam,
                    timestamp=now,
                    duration_s=dwell,
                    details=f"Object loitered for {dwell:.1f}s (threshold: {self._loiter_threshold}s)",
                ))
                break

        return violations

    def check_path_reversal(self, object_id: str) -> List[SuspiciousActivity]:
        """Check if object changed heading by > threshold angle."""
        positions = self._positions.get(object_id, [])
        if len(positions) < 3:
            return []

        now = positions[-1][2]
        # Filter to recent window
        recent = [(x, y, t, c) for x, y, t, c in positions if now - t <= self._reversal_window]
        if len(recent) < 3:
            return []

        # Calculate heading changes
        headings = []
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            dy = recent[i][1] - recent[i-1][1]
            heading = math.atan2(dy, dx)
            headings.append((heading, recent[i][2], recent[i][3]))

        violations = []
        for i in range(1, len(headings)):
            angle_diff = abs(headings[i][0] - headings[i-1][0])
            angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
            angle_deg = math.degrees(angle_diff)
            if angle_deg >= self._reversal_angle:
                violations.append(SuspiciousActivity(
                    activity_type="path_reversal",
                    object_id=object_id,
                    camera_id=headings[i][2],
                    timestamp=headings[i][1],
                    details=f"Heading changed by {angle_deg:.1f} degrees (threshold: {self._reversal_angle})",
                ))
                break

        return violations

    def check_group_clustering(self) -> List[SuspiciousActivity]:
        """Check if N+ objects are within radius for > threshold time."""
        if len(self._positions) < self._cluster_min:
            return []

        violations = []
        checked = set()

        # Get latest position for each object
        latest = {}
        for obj_id, positions in self._positions.items():
            if positions:
                x, y, ts, cam = positions[-1]
                latest[obj_id] = (x, y, ts, cam)

        obj_ids = list(latest.keys())
        for i in range(len(obj_ids)):
            for j in range(i + 1, len(obj_ids)):
                a_id, b_id = obj_ids[i], obj_ids[j]
                pair_key = tuple(sorted([a_id, b_id]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)

                ax, ay, _, _ = latest[a_id]
                bx, by, _, _ = latest[b_id]
                dist = math.sqrt((ax - bx)**2 + (ay - by)**2)

                if dist <= self._cluster_radius:
                    # Check how long they've been close — find the
                    # earliest and latest timestamps where both are within radius
                    a_positions = self._positions[a_id]
                    b_positions = self._positions[b_id]
                    if len(a_positions) < 2 or len(b_positions) < 2:
                        continue

                    # Build sets of timestamps where each object is within radius of the other
                    close_times = set()
                    for ax, ay, at, _ in a_positions:
                        for bx, by, bt, _ in b_positions:
                            pair_dist = math.sqrt((ax - bx)**2 + (ay - by)**2)
                            if pair_dist <= self._cluster_radius:
                                close_times.add(at)

                    if len(close_times) < 2:
                        continue

                    duration = max(close_times) - min(close_times)
                    if duration >= self._cluster_threshold:
                        violations.append(SuspiciousActivity(
                            activity_type="group_clustering",
                            object_id=f"{a_id},{b_id}",
                            camera_id=latest[a_id][3],
                            timestamp=max(close_times),
                            duration_s=duration,
                            details=f"{len([a_id, b_id])} objects within {self._cluster_radius} for {duration:.1f}s",
                        ))

        return violations
