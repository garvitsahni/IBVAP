"""Tests for watchlist matching at detection time."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def test_match_detection_no_watchlist():
    """No watchlist entries → no match."""
    from fusion_server.services.watchlist_matcher import WatchlistMatcher

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []

    matcher = WatchlistMatcher()
    embedding = np.random.rand(512).astype(np.float32)
    result = matcher.match_detection(mock_db, embedding, "person")
    assert result is None


def test_match_detection_matching_embedding():
    """Matching embedding returns match with reference_id."""
    from fusion_server.services.watchlist_matcher import WatchlistMatcher
    from fusion_server.core.watchlist_crypto import encrypt_embedding, get_key

    key = get_key()
    target_emb = np.random.rand(512).astype(np.float32)
    target_emb = target_emb / np.linalg.norm(target_emb)

    # Create mock watchlist entry
    mock_entry = MagicMock()
    mock_entry.watchlist_type = "face"
    mock_entry.reference_id = "suspect-001"
    mock_entry.embedding = encrypt_embedding(target_emb.tolist(), key)
    mock_entry.active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_entry]

    matcher = WatchlistMatcher(threshold_person=0.5)
    result = matcher.match_detection(mock_db, target_emb, "person")

    assert result is not None
    assert result["reference_id"] == "suspect-001"
    assert result["similarity"] > 0.99


def test_match_detection_below_threshold():
    """Embedding below threshold returns no match."""
    from fusion_server.services.watchlist_matcher import WatchlistMatcher
    from fusion_server.core.watchlist_crypto import encrypt_embedding, get_key

    key = get_key()
    target_emb = np.random.rand(512).astype(np.float32)
    target_emb = target_emb / np.linalg.norm(target_emb)

    mock_entry = MagicMock()
    mock_entry.watchlist_type = "face"
    mock_entry.reference_id = "suspect-001"
    mock_entry.embedding = encrypt_embedding(target_emb.tolist(), key)
    mock_entry.active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = [mock_entry]

    # Query embedding is completely different
    query_emb = -np.random.rand(512).astype(np.float32)
    query_emb = query_emb / np.linalg.norm(query_emb)

    matcher = WatchlistMatcher(threshold_person=0.9)
    result = matcher.match_detection(mock_db, query_emb, "person")
    assert result is None
