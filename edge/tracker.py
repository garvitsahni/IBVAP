"""
ByteTrack-inspired per-camera tracker.
SORT-style Kalman filter + Hungarian assignment.
If yolox is available, uses its BYTETracker. Otherwise, self-contained impl.
"""
import numpy as np
from dataclasses import dataclass
from typing import List

try:
    from yolox.tracker.byte_tracker import BYTETracker as _ByteTracker
    _HAS_YOLOX = True
except ImportError:
    _HAS_YOLOX = False


@dataclass
class TrackedObject:
    track_id: int
    bbox: List[float]  # [x1, y1, x2, y2] pixel coords
    class_id: int
    class_name: str
    confidence: float


class _KalmanBoxTracker:
    """Single-object Kalman filter for bounding box tracking."""
    _id_counter = 0

    def __init__(self, bbox: List[float], class_id: int, class_name: str, confidence: float):
        self.track_id = _KalmanBoxTracker._id_counter
        _KalmanBoxTracker._id_counter += 1

        self.class_id = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.hits = 1
        self.time_since_update = 0

        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        self.x = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=np.float64)

        self.P = np.eye(8) * 10.0
        self.P[4:, 4:] *= 100.0

        self.F = np.eye(8)
        self.F[0, 4] = 1
        self.F[1, 5] = 1
        self.F[2, 6] = 1
        self.F[3, 7] = 1

        self.H = np.zeros((4, 8))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        self.H[3, 3] = 1

        self.R = np.eye(4) * 10.0
        self.Q = np.eye(8) * 1.0
        self.Q[4:, 4:] *= 0.01

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        self.x[2] = max(1.0, self.x[2])
        self.x[3] = max(1.0, self.x[3])

    def update(self, bbox: List[float]):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        z = np.array([cx, cy, w, h])

        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(8) - K @ self.H) @ self.P

        self.hits += 1
        self.time_since_update = 0

    def get_bbox(self) -> List[float]:
        cx, cy, w, h = self.x[0], self.x[1], self.x[2], self.x[3]
        return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]

    @property
    def age(self):
        return self.hits


def _iou_batch(bb_test, bb_gt):
    """Compute IoU between two sets of boxes."""
    if len(bb_test) == 0 or len(bb_gt) == 0:
        return np.zeros((len(bb_test), len(bb_gt)))

    xx1 = np.maximum(bb_test[:, 0:1], bb_gt[:, 0:1].T)
    yy1 = np.maximum(bb_test[:, 1:2], bb_gt[:, 1:2].T)
    xx2 = np.minimum(bb_test[:, 2:3], bb_gt[:, 2:3].T)
    yy2 = np.minimum(bb_test[:, 3:4], bb_gt[:, 3:4].T)

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    inter = w * h

    area_test = (bb_test[:, 2] - bb_test[:, 0]) * (bb_test[:, 3] - bb_test[:, 1])
    area_gt = (bb_gt[:, 2] - bb_gt[:, 0]) * (bb_gt[:, 3] - bb_gt[:, 1])

    union = area_test[:, None] + area_gt[None, :] - inter
    return inter / np.maximum(union, 1e-6)


def _linear_assignment(cost_matrix):
    """Hungarian algorithm via scipy."""
    from scipy.optimize import linear_sum_assignment
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return np.array(list(zip(row_ind, col_ind)))


class _SimpleByteTracker:
    """Self-contained ByteTrack-style tracker (SORT + low-confidence matching)."""

    def __init__(self, track_thresh: float = 0.5, match_thresh: float = 0.8, max_age: int = 30):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.max_age = max_age
        self.trackers: List[_KalmanBoxTracker] = []

    def update(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        for trk in self.trackers:
            trk.predict()

        if len(detections) == 0:
            self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_age]
            return []

        high_conf = [d for d in detections if d["confidence"] >= self.track_thresh]
        low_conf = [d for d in detections if d["confidence"] < self.track_thresh and d["confidence"] >= 0.1]

        matched, unmatched_dets, unmatched_trks = self._match(
            [d["bbox"] for d in high_conf],
            [t.get_bbox() for t in self.trackers],
            self.match_thresh
        )

        matched_trk_indices = set()
        for d_idx, t_idx in matched:
            self.trackers[t_idx].update(high_conf[d_idx]["bbox"])
            self.trackers[t_idx].class_id = high_conf[d_idx]["class_id"]
            self.trackers[t_idx].class_name = high_conf[d_idx]["class_name"]
            self.trackers[t_idx].confidence = high_conf[d_idx]["confidence"]
            matched_trk_indices.add(t_idx)

        new_track_ids = set()
        for d_idx in unmatched_dets:
            d = high_conf[d_idx]
            new_trk = _KalmanBoxTracker(d["bbox"], d["class_id"], d["class_name"], d["confidence"])
            new_track_ids.add(new_trk.track_id)
            self.trackers.append(new_trk)

        remaining_trks = [i for i in unmatched_trks if i not in matched_trk_indices]
        if len(low_conf) > 0 and len(remaining_trks) > 0:
            low_matched, _, _ = self._match(
                [d["bbox"] for d in low_conf],
                [self.trackers[i].get_bbox() for i in remaining_trks],
                self.match_thresh * 0.9
            )
            for d_idx, t_idx in low_matched:
                trk_idx = remaining_trks[t_idx]
                self.trackers[trk_idx].update(low_conf[d_idx]["bbox"])
                self.trackers[trk_idx].confidence = low_conf[d_idx]["confidence"]

        self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_age]

        for trk in self.trackers:
            if trk.track_id not in new_track_ids and trk.track_id not in {self.trackers[i].track_id for i in matched_trk_indices}:
                trk.time_since_update += 1

        results = []
        for trk in self.trackers:
            if trk.time_since_update == 0:
                bbox = trk.get_bbox()
                results.append(TrackedObject(
                    track_id=trk.track_id,
                    bbox=bbox,
                    class_id=trk.class_id,
                    class_name=trk.class_name,
                    confidence=trk.confidence,
                ))
        return results

    def _match(self, detections, trackers, threshold):
        if len(detections) == 0 or len(trackers) == 0:
            return [], list(range(len(detections))), list(range(len(trackers)))

        det_array = np.array(detections)
        trk_array = np.array(trackers)

        iou_matrix = _iou_batch(det_array, trk_array)
        cost_matrix = 1.0 - iou_matrix

        try:
            matches = _linear_assignment(cost_matrix)
        except Exception:
            return [], list(range(len(detections))), list(range(len(trackers)))

        matched = []
        unmatched_dets = set(range(len(detections)))
        unmatched_trks = set(range(len(trackers)))

        for d_idx, t_idx in matches:
            if iou_matrix[d_idx, t_idx] >= (1.0 - threshold):
                matched.append((d_idx, t_idx))
                unmatched_dets.discard(d_idx)
                unmatched_trks.discard(t_idx)

        return matched, list(unmatched_dets), list(unmatched_trks)


class Tracker:
    """Per-camera ByteTrack tracker. Uses yolox if available, else self-contained."""

    def __init__(self):
        if _HAS_YOLOX:
            from yolox.tracker.byte_tracker import BYTETrackerArgs
            args = BYTETrackerArgs(track_thresh=0.5, match_thresh=0.8)
            self._tracker = _ByteTracker(args)
            self._use_yolox = True
        else:
            self._tracker = _SimpleByteTracker()
            self._use_yolox = False

    def update(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        if self._use_yolox:
            return self._update_yolox(detections, frame_shape)
        else:
            return self._tracker.update(detections, frame_shape)

    def _update_yolox(self, detections: List[dict], frame_shape: tuple) -> List[TrackedObject]:
        import torch
        if len(detections) == 0:
            dets_np = np.zeros((0, 5), dtype=np.float32)
        else:
            dets_np = np.array([
                [d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3], d["confidence"]]
                for d in detections
            ], dtype=np.float32)

        online_targets = self._tracker.update(
            torch.from_numpy(dets_np),
            torch.from_numpy(np.array(frame_shape)),
            torch.from_numpy(np.array(frame_shape))
        )

        results = []
        for t in online_targets:
            tlwh = t.tlwh
            bbox = [tlwh[0], tlwh[1], tlwh[0] + tlwh[2], tlwh[1] + tlwh[3]]
            results.append(TrackedObject(
                track_id=t.track_id,
                bbox=bbox,
                class_id=t.class_id if hasattr(t, 'class_id') else 0,
                class_name=t.class_name if hasattr(t, 'class_name') else "person",
                confidence=t.score if hasattr(t, 'score') else 0.0,
            ))
        return results
