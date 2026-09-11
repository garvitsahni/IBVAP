"""Tests for alert hash chain linkage."""
import pytest
from datetime import datetime
from fusion_server.core.alert_ledger import AlertLedger


def test_alert_ledger_computes_hash():
    """AlertLedger computes hash for alert fields."""
    h = AlertLedger.compute_alert_hash(
        alert_id="alert-001",
        object_id="obj-001",
        camera_id="cam1",
        timestamp="2026-09-11T10:00:00",
        reason="virtual_fence_crossing",
        previous_hash=None,
    )
    assert len(h) == 64  # SHA-256 hex
    assert h != ""


def test_alert_ledger_hash_includes_previous_hash():
    """Different previous_hash produces different hash."""
    h1 = AlertLedger.compute_alert_hash("a1", "o1", "cam1", "t1", "reason1", None)
    h2 = AlertLedger.compute_alert_hash("a1", "o1", "cam1", "t1", "reason1", "prev_hash")
    assert h1 != h2


def test_alert_ledger_write_alert():
    """write_alert_with_hash sets hash and previous_hash on alert."""
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = None

    alert = MagicMock()
    alert.alert_id = "alert-001"
    alert.object_id = "obj-001"
    alert.camera_id = "cam1"
    alert.timestamp = datetime(2026, 9, 11, 10, 0, 0)
    alert.reason = "virtual_fence_crossing"
    alert.hash = None
    alert.previous_hash = None

    ledger = AlertLedger()
    ledger.write_alert_with_hash(mock_db, alert)

    assert alert.hash is not None
    assert len(alert.hash) == 64
    assert alert.previous_hash is None  # First alert
    mock_db.commit.assert_called_once()


def test_alert_ledger_links_previous_hash():
    """Second alert gets previous_hash from last alert."""
    from unittest.mock import MagicMock, PropertyMock

    mock_db = MagicMock()

    last_alert = MagicMock()
    last_alert.hash = "abc123" + "0" * 58  # 64 char hash

    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.first.return_value = last_alert

    alert = MagicMock()
    alert.alert_id = "alert-002"
    alert.object_id = "obj-001"
    alert.camera_id = "cam1"
    alert.timestamp = datetime(2026, 9, 11, 10, 5, 0)
    alert.reason = "virtual_fence_crossing"
    alert.hash = None
    alert.previous_hash = None

    ledger = AlertLedger()
    ledger.write_alert_with_hash(mock_db, alert)

    assert alert.previous_hash == "abc123" + "0" * 58
    assert alert.hash is not None
    assert len(alert.hash) == 64


def test_alert_ledger_hash_deterministic():
    """Same inputs produce same hash."""
    h1 = AlertLedger.compute_alert_hash("a1", "o1", "cam1", "t1", "reason1", None)
    h2 = AlertLedger.compute_alert_hash("a1", "o1", "cam1", "t1", "reason1", None)
    assert h1 == h2
