"""Tests for event publisher — verifies ARCHITECTURE.md §5 contract."""

def test_builds_correct_event_json():
    """Event JSON matches the frozen DetectionEvent contract."""
    from edge.event_publisher import EventPublisher

    pub = EventPublisher("http://localhost:9999")
    event = pub.build_event(
        camera_id="cam1",
        timestamp="2026-09-10T12:00:00Z",
        object_type="person",
        track_id="42",
        bbox_pixels=[100, 50, 300, 400],
        frame_shape=(480, 640),
        confidence=0.92,
    )

    assert event["camera_id"] == "cam1"
    assert event["timestamp"] == "2026-09-10T12:00:00Z"
    assert event["object_type"] == "person"
    assert event["track_id"] == "42"
    assert event["confidence"] == 0.92
    assert event["embedding"] is None

    assert len(event["bbox"]) == 4
    bbox = event["bbox"]
    x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
    assert 0 <= x1 <= 1
    assert 0 <= y1 <= 1
    assert 0 < x2 <= 1
    assert 0 < y2 <= 1

    assert abs(x1 - 100/640) < 0.001
    assert abs(y1 - 50/480) < 0.001
    assert abs(x2 - 300/640) < 0.001
    assert abs(y2 - 400/480) < 0.001


def test_object_type_mapping():
    """Vehicle COCO classes map to 'vehicle'."""
    from edge.event_publisher import EventPublisher

    pub = EventPublisher("http://localhost:9999")
    for cls_id, expected_type in [(2, "vehicle"), (3, "vehicle"), (5, "vehicle"), (7, "vehicle"), (0, "person")]:
        event = pub.build_event(
            camera_id="cam1",
            timestamp="2026-09-10T12:00:00Z",
            object_type="person" if cls_id == 0 else "vehicle",
            track_id="1",
            bbox_pixels=[100, 100, 200, 200],
            frame_shape=(480, 640),
            confidence=0.9,
        )
        assert event["object_type"] == expected_type


def test_publish_returns_false_on_failure():
    """Publish returns False when server unreachable."""
    from edge.event_publisher import EventPublisher

    pub = EventPublisher("http://localhost:19999")
    result = pub.publish({"camera_id": "cam1", "timestamp": "2026-09-10T12:00:00Z"})
    assert result is False
