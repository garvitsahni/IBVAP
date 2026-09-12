"""Blind-spot computation — FOV minus ROI union."""
from typing import List, Dict
from shapely.geometry import Polygon
from shapely.ops import unary_union
from fusion_server.core.rule_engine import ROI

DEFAULT_FOV = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def compute_blind_spots(
    cameras: List[Dict],
    rois: List[ROI],
) -> Dict[str, Dict]:
    """
    For each camera, compute blind spots as FOV minus the union of all ROIs.
    """
    result = {}
    for cam in cameras:
        cam_id = cam["camera_id"]
        fov_poly = Polygon(cam.get("fov_polygon", DEFAULT_FOV))

        cam_rois = [r for r in rois if r.camera_id == cam_id or r.camera_id == "*"]
        if cam_rois:
            roi_polys = [Polygon(r.polygon) for r in cam_rois]
            covered = unary_union(roi_polys)
            blind_area = fov_poly.difference(covered)
        else:
            covered = Polygon()
            blind_area = fov_poly

        blind_polygons = _extract_polygons(blind_area)
        is_fully_covered = blind_area.is_empty

        result[cam_id] = {
            "fov_polygon": list(fov_poly.exterior.coords),
            "covered_union": _extract_polygons(covered) if not covered.is_empty else [],
            "blind_spots": blind_polygons,
            "is_fully_covered": is_fully_covered,
        }

    return result


def _extract_polygons(geom):
    """Extract list of polygon coordinate lists from a Shapely geometry."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)]
    elif geom.geom_type == "MultiPolygon":
        return [list(p.exterior.coords) for p in geom.geoms]
    return []
