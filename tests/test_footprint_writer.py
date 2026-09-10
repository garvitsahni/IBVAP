"""Tests for FootprintChainWriter — footprint chain with hash linkage."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch


def test_footprint_writer_initializes():
    """FootprintChainWriter can be instantiated."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()
    assert writer is not None


def test_footprint_writer_first_seen():
    """FootprintChainWriter creates first_seen entry for new object."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 0),
        event_type="first_seen",
        detection_event_id=1,
    )

    assert entry is not None
    assert entry["event_type"] == "first_seen"
    assert entry["previous_hash"] is None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_footprint_writer_hop_different_camera():
    """FootprintChainWriter creates hop entry when camera changes."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.event_type = "first_seen"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_last_entry]

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam2",
        timestamp=datetime(2026, 9, 11, 10, 5, 0),
        event_type="hop",
        detection_event_id=2,
    )

    assert entry is not None
    assert entry["event_type"] == "hop"
    assert entry["previous_hash"] == "abc123"


def test_footprint_writer_same_camera_no_hop():
    """FootprintChainWriter skips hop when same camera and recent."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    mock_last_entry = MagicMock()
    mock_last_entry.camera_id = "cam1"
    mock_last_entry.hash = "abc123"
    mock_last_entry.timestamp = datetime(2026, 9, 11, 10, 0, 0)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_last_entry]

    entry = writer.write_entry(
        db=mock_db,
        object_id="obj-123",
        camera_id="cam1",
        timestamp=datetime(2026, 9, 11, 10, 0, 1),
        event_type="hop",
        detection_event_id=3,
    )

    assert entry is None
    mock_db.add.assert_not_called()


def test_footprint_writer_hash_chain():
    """FootprintChainWriter computes hash correctly."""
    from fusion_server.services.footprint_writer import FootprintChainWriter
    writer = FootprintChainWriter()

    hash_value = writer._compute_hash(
        object_id="obj-123",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        event_type="first_seen",
        previous_hash=None,
    )

    assert hash_value is not None
    assert len(hash_value) == 64
