"""Integration test: full pipeline on synthetic video."""

def test_full_pipeline_synthetic_video():
    """
    Feed a synthetic video through the full pipeline:
    ingestion -> night/weather -> detection -> tracking -> event building.
    Verifies events match ARCHITECTURE.md §5 contract.
    """
    import numpy as np
    import cv2
    from edge.night_weather import NightWeatherProcessor
    from edge.tracker import Tracker
    from edge.event_publisher import EventPublisher

    frames = []
    for i in range(5):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        x = 100 + i * 50
        cv2.rectangle(frame, (x, 100), (x + 100, 400), (255, 255, 255), -1)
        frames.append(frame)

    nw = NightWeatherProcessor()
    tracker = Tracker()
    publisher = EventPublisher("http://localhost:9999")

    all_events = []
    for i, frame in enumerate(frames):
        processed, mode_info = nw.process(frame)

        h, w = frame.shape[:2]
        x = 100 + i * 50
        fake_detections = [{
            "bbox": [float(x), 100.0, float(x + 100), 400.0],
            "confidence": 0.9,
            "class_id": 0,
            "class_name": "person",
        }]

        tracks = tracker.update(fake_detections, (h, w))
        assert len(tracks) >= 1

        for track in tracks:
            event = publisher.build_event(
                camera_id="cam1",
                timestamp=f"2026-09-10T12:00:0{i}Z",
                object_type="person",
                track_id=str(track.track_id),
                bbox_pixels=track.bbox,
                frame_shape=(h, w),
                confidence=track.confidence,
            )
            all_events.append(event)

    assert len(all_events) > 0
    for event in all_events:
        assert "camera_id" in event
        assert "timestamp" in event
        assert "object_type" in event
        assert "track_id" in event
        assert "bbox" in event
        assert "embedding" in event and event["embedding"] is None
        assert "confidence" in event
        assert event["object_type"] in ("person", "vehicle")
        assert len(event["bbox"]) == 4
        assert all(0 <= v <= 1 for v in event["bbox"])
