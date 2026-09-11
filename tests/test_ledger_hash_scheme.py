"""Tests for canonical hash scheme consistency."""
import hashlib
import pytest
from fusion_server.core.ledger import compute_hash, verify_chain, append_entry


def test_compute_hash_includes_previous_hash():
    """Hash includes previous_hash in computation."""
    h1 = compute_hash("obj1cam12026-09-11T10:00:00first_seen")
    h2 = compute_hash("obj1cam12026-09-11T10:00:00first_seen" + "prev_hash_abc")
    assert h1 != h2, "previous_hash must affect the hash"


def test_append_entry_produces_verifiable_hash():
    """Entry from append_entry passes verify_chain."""
    entry = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    is_valid, idx = verify_chain([entry])
    assert is_valid is True
    assert idx is None


def test_verify_chain_detects_tampered_hash():
    """Tampered hash is detected by verify_chain."""
    entry = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    entry["hash"] = "tampered"
    is_valid, idx = verify_chain([entry])
    assert is_valid is False
    assert idx == 0


def test_verify_chain_detects_tampered_previous_hash():
    """Tampered previous_hash linkage is detected."""
    e1 = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    e2 = append_entry("obj1", "cam2", "2026-09-11T10:05:00", "hop", e1["hash"])
    e2["previous_hash"] = "tampered"
    is_valid, idx = verify_chain([e1, e2])
    assert is_valid is False
    assert idx == 1


def test_verify_chain_valid_multi_entry():
    """Chain of 3 entries with correct linkage passes."""
    e1 = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    e2 = append_entry("obj1", "cam2", "2026-09-11T10:05:00", "hop", e1["hash"])
    e3 = append_entry("obj1", "cam3", "2026-09-11T10:10:00", "hop", e2["hash"])
    is_valid, idx = verify_chain([e1, e2, e3])
    assert is_valid is True
    assert idx is None


def test_append_entry_matches_footprint_writer_scheme():
    """append_entry uses same hash scheme as FootprintChainWriter._compute_hash."""
    # Simulate what FootprintChainWriter._compute_hash does
    def writer_hash(object_id, camera_id, timestamp, event_type, previous_hash):
        data = f"{object_id}{camera_id}{timestamp}{event_type}"
        if previous_hash:
            data += previous_hash
        return hashlib.sha256(data.encode()).hexdigest()

    # First entry (no previous_hash)
    entry1 = append_entry("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    expected1 = writer_hash("obj1", "cam1", "2026-09-11T10:00:00", "first_seen", None)
    assert entry1["hash"] == expected1

    # Second entry (with previous_hash)
    entry2 = append_entry("obj1", "cam2", "2026-09-11T10:05:00", "hop", entry1["hash"])
    expected2 = writer_hash("obj1", "cam2", "2026-09-11T10:05:00", "hop", entry1["hash"])
    assert entry2["hash"] == expected2
