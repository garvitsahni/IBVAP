"""Tests for ByteTrack tracker wrapper."""

def test_tracker_assigns_ids():
    """Same object across frames gets same track ID."""
    from edge.tracker import Tracker
    tracker = Tracker()
    det1 = [{"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9}]
    tracks1 = tracker.update(det1, (480, 640))
    assert len(tracks1) == 1
    tid1 = tracks1[0].track_id

    det2 = [{"bbox": [105, 102, 205, 302], "class_id": 0, "class_name": "person", "confidence": 0.88}]
    tracks2 = tracker.update(det2, (480, 640))
    assert len(tracks2) == 1
    assert tracks2[0].track_id == tid1


def test_tracker_multiple_objects():
    """Multiple objects get distinct IDs."""
    from edge.tracker import Tracker
    tracker = Tracker()
    dets = [
        {"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9},
        {"bbox": [400, 100, 500, 300], "class_id": 2, "class_name": "car", "confidence": 0.85},
    ]
    tracks = tracker.update(dets, (480, 640))
    assert len(tracks) == 2
    ids = {t.track_id for t in tracks}
    assert len(ids) == 2


def test_tracker_lost_track_cleanup():
    """Track that receives no detections for 30 frames is removed."""
    from edge.tracker import Tracker
    tracker = Tracker()
    det = [{"bbox": [100, 100, 200, 300], "class_id": 0, "class_name": "person", "confidence": 0.9}]
    tracks = tracker.update(det, (480, 640))
    active_id = tracks[0].track_id

    for _ in range(31):
        tracks = tracker.update([], (480, 640))

    active_ids = {t.track_id for t in tracks}
    assert active_id not in active_ids


def test_tracker_empty_frame():
    """Empty detections produce empty tracks."""
    from edge.tracker import Tracker
    tracker = Tracker()
    tracks = tracker.update([], (480, 640))
    assert tracks == []
