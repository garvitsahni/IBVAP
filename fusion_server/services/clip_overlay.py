"""
Task 22: Clip Overlay Renderer — OpenCV burn-in for alert video clips.

Overlays ROI geometry, camera ID, timestamp, and threat score onto video frames.
Pure computer vision — no ML model inference, no alert decisions.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional


COLOR_CRITICAL = (0, 0, 255)   # Red (BGR)
COLOR_HIGH = (0, 165, 255)     # Orange
COLOR_MEDIUM = (0, 255, 255)   # Yellow
COLOR_LOW = (128, 128, 128)    # Gray
COLOR_ROI = (0, 255, 0)        # Green for ROI polygon
COLOR_TEXT_BG = (0, 0, 0)      # Black background for text


def _threat_color(score: float) -> tuple[int, int, int]:
    if score >= 0.8:
        return COLOR_CRITICAL
    if score >= 0.5:
        return COLOR_HIGH
    if score >= 0.3:
        return COLOR_MEDIUM
    return COLOR_LOW


def _severity_label(score: float) -> str:
    if score >= 0.8:
        return "CRITICAL"
    if score >= 0.5:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


def overlay_roi_polygon(
    frame: np.ndarray,
    roi_polygon: list[list[float]],
    color: tuple[int, int, int] = COLOR_ROI,
    thickness: int = 2,
) -> np.ndarray:
    """Draw ROI polygon on frame. Polygon coords are normalized [0,1]."""
    h, w = frame.shape[:2]
    pts = np.array([[int(x * w), int(y * h)] for x, y in roi_polygon], dtype=np.int32)
    if len(pts) >= 3:
        cv2.polylines(frame, [pts], True, color, thickness, cv2.LINE_AA)
    return frame


def overlay_text_with_bg(
    frame: np.ndarray,
    text: str,
    position: tuple[int, int],
    font_scale: float = 0.5,
    color: tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
) -> np.ndarray:
    """Draw text with black background for readability."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position
    cv2.rectangle(frame, (x - 2, y - th - 4), (x + tw + 4, y + baseline + 2), COLOR_TEXT_BG, -1)
    cv2.putText(frame, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)
    return frame


def render_overlay(
    input_path: str,
    output_path: str,
    camera_id: str,
    timestamp: str,
    threat_score: float,
    roi_polygon: Optional[list[list[float]]] = None,
    reason: str = "",
) -> str:
    """
    Render alert overlay onto a video clip. Burns in:
    - ROI polygon geometry
    - Camera ID, timestamp, threat score, severity label
    - Reason text (if provided)

    Args:
        input_path: Path to source video clip.
        output_path: Path for output video with overlays.
        camera_id: Camera identifier to display.
        timestamp: Timestamp string to display.
        threat_score: Threat score for severity coloring.
        roi_polygon: Optional ROI polygon in normalized [0,1] coords.
        reason: Optional alert reason text.

    Returns:
        The output_path string.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    threat_color = _threat_color(threat_score)
    severity = _severity_label(threat_score)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # ROI polygon overlay
        if roi_polygon:
            frame = overlay_roi_polygon(frame, roi_polygon, COLOR_ROI)

        # Top-left: camera ID + timestamp
        frame = overlay_text_with_bg(frame, f"Camera: {camera_id}", (8, 24), 0.6, (255, 255, 255))
        frame = overlay_text_with_bg(frame, f"Time: {timestamp}", (8, 50), 0.5, (200, 200, 200))

        # Top-right: threat score + severity
        score_text = f"{severity} ({threat_score:.2f})"
        (tw, _), _ = cv2.getTextSize(score_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        frame = overlay_text_with_bg(frame, score_text, (width - tw - 12, 28), 0.7, threat_color, 2)

        # Bottom-left: reason (if present)
        if reason:
            frame = overlay_text_with_bg(frame, reason, (8, height - 16), 0.5, (200, 200, 200))

        # Bottom-right: frame counter
        frame = overlay_text_with_bg(frame, f"Frame {frame_idx}", (width - 90, height - 16), 0.4, (128, 128, 128))

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()
    return output_path
