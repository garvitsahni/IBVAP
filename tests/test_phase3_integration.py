# tests/test_phase3_integration.py
"""Integration tests for Phase 3 — all three exit criteria."""
import numpy as np
import pytest
from datetime import datetime


def test_exit_criteria_a_tamper_detection():
    """Exit criteria (a): Tamper with ledger entry, verify detection."""
    from fusion_server.core.ledger import append_entry, verify_chain

    # Build a valid chain
    e1 = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    e2 = append_entry("obj1", "cam2", "2026-09-11T10:05:00", "hop", e1["hash"])
    e3 = append_entry("obj1", "cam3", "2026-09-11T10:10:00", "hop", e2["hash"])

    # Verify valid
    is_valid, _ = verify_chain([e1, e2, e3])
    assert is_valid, "Chain should be valid before tampering"

    # Tamper with middle entry (simulate direct DB edit — hash not recomputed)
    e2["camera_id"] = "cam99"

    # Verify broken
    is_valid, broken_idx = verify_chain([e1, e2, e3])
    assert not is_valid, "Chain should be broken after tampering"
    assert broken_idx == 1, "Tampering should be detected at index 1"


def test_exit_criteria_b_camera_compromise():
    """Exit criteria (b): Camera compromise detection."""
    from edge.camera_health import CameraHealthService

    svc = CameraHealthService(camera_id="cam1")

    # Normal frame — no compromise
    normal_frame = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
    darkness = svc.check_darkness(normal_frame)
    assert darkness["status"] == "ok"

    # Blinding — cover the lens (dark frame)
    dark_frame = np.zeros((480, 640, 3), dtype=np.uint8) + 5
    darkness = svc.check_darkness(dark_frame)
    assert darkness["status"] == "blinding"

    # Blurry — obscured lens
    import cv2
    blurry_frame = cv2.GaussianBlur(normal_frame, (51, 51), 30)
    blur = svc.check_blur(blurry_frame)
    assert blur["status"] == "obscured"

    # Frozen — same frame twice
    frozen = svc.check_frozen(normal_frame, normal_frame.copy())
    assert frozen["status"] == "frozen"


def test_exit_criteria_c_watchlist_match():
    """Exit criteria (c): Watchlist match fires correctly."""
    from fusion_server.services.watchlist_matcher import WatchlistMatcher
    from fusion_server.core.watchlist_crypto import encrypt_embedding, get_key
    from unittest.mock import MagicMock

    key = get_key()
    target_emb = np.random.rand(512).astype(np.float32)
    target_emb = target_emb / np.linalg.norm(target_emb)

    mock_entry = MagicMock()
    mock_entry.watchlist_type = "face"
    mock_entry.reference_id = "known-suspect-001"
    mock_entry.embedding = encrypt_embedding(target_emb.tolist(), key)
    mock_entry.active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_entry]

    matcher = WatchlistMatcher(threshold_person=0.5)
    result = matcher.match_detection(mock_db, target_emb, "person")

    assert result is not None
    assert result["reference_id"] == "known-suspect-001"
    assert result["similarity"] > 0.99
