"""
Deterministic Rule Engine - Core differentiator per ARCHITECTURE.md
Only this module (not ML) decides alert.status = fired
"""
from dataclasses import dataclass
from typing import List, Optional
from shapely.geometry import Point, Polygon


@dataclass
class ROI:
    """Region of Interest - virtual fence or restricted zone."""
    camera_id: str
    name: str
    polygon: List[List[float]]  # [[x1,y1], [x2,y2], ...] normalized 0-1
    alert_on_enter: bool = True
    alert_on_exit: bool = False
    object_types: List[str] = None  # None = all types


@dataclass
class RuleViolation:
    """A deterministic rule violation that fires an alert."""
    object_id: str
    camera_id: str
    timestamp: str
    roi_name: str
    violation_type: str  # "enter" | "exit" | "dwell" | "speed" | "direction"
    threat_score: float  # 0.0 - 1.0


class RuleEngine:
    """
    Deterministic rule engine for alert generation.
    NO ML involved - pure geometry and threshold logic.
    """

    def __init__(self):
        self.rois: List[ROI] = []

    def add_roi(self, roi: ROI):
        """Add a region of interest."""
        self.rois.append(roi)

    def check_roi_intrusion(
        self,
        object_id: str,
        camera_id: str,
        timestamp: str,
        bbox: dict,
        object_type: str,
        previous_bbox: Optional[dict] = None,
    ) -> List[RuleViolation]:
        """
        Check if object centroid violates any ROI for this camera.
        Returns list of violations (empty if none).
        """
        violations = []

        # Calculate centroid of bbox (normalized 0-1)
        centroid_x = (bbox["x1"] + bbox["x2"]) / 2
        centroid_y = (bbox["y1"] + bbox["y2"]) / 2
        point = Point(centroid_x, centroid_y)

        for roi in self.rois:
            if roi.camera_id != camera_id:
                continue
            if roi.object_types and object_type not in roi.object_types:
                continue

            polygon = Polygon(roi.polygon)
            is_inside = polygon.contains(point)

            if is_inside and roi.alert_on_enter:
                violations.append(RuleViolation(
                    object_id=object_id,
                    camera_id=camera_id,
                    timestamp=timestamp,
                    roi_name=roi.name,
                    violation_type="enter",
                    threat_score=0.5,  # Base score, adjusted by threat_scoring
                ))
            elif not is_inside and previous_bbox and roi.alert_on_exit:
                prev_centroid_x = (previous_bbox["x1"] + previous_bbox["x2"]) / 2
                prev_centroid_y = (previous_bbox["y1"] + previous_bbox["y2"]) / 2
                prev_point = Point(prev_centroid_x, prev_centroid_y)
                if polygon.contains(prev_point):
                    violations.append(RuleViolation(
                        object_id=object_id,
                        camera_id=camera_id,
                        timestamp=timestamp,
                        roi_name=roi.name,
                        violation_type="exit",
                        threat_score=0.4,
                    ))

        return violations

    def check_virtual_fence(
        self,
        object_id: str,
        camera_id: str,
        timestamp: str,
        bbox: dict,
        object_type: str,
        previous_bbox: Optional[dict] = None,
    ) -> List[RuleViolation]:
        """Alias for check_roi_intrusion - virtual fence is just an ROI."""
        return self.check_roi_intrusion(object_id, camera_id, timestamp, bbox, object_type, previous_bbox)