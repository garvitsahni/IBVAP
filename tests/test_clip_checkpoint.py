"""Tests for ClipCheckpoint — pending/complete markers for clips."""
import pytest
import os
from fusion_server.services.clip_checkpoint import ClipCheckpoint


def test_mark_pending_creates_marker(tmp_path):
    """mark_pending creates a .pending file."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-42")
    assert (tmp_path / "clips" / "alert-42.pending").exists()


def test_mark_complete_removes_marker(tmp_path):
    """mark_complete removes the .pending file."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-42")
    cp.mark_complete("alert-42")
    assert not (tmp_path / "clips" / "alert-42.pending").exists()


def test_scan_orphans_finds_pending(tmp_path):
    """scan_orphans finds .pending files."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("alert-1")
    cp.mark_pending("alert-2")
    orphans = cp.scan_orphans()
    assert len(orphans) == 2
    assert "alert-1" in orphans
    assert "alert-2" in orphans


def test_scan_orphans_empty(tmp_path):
    """scan_orphans returns empty when no orphans."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    orphans = cp.scan_orphans()
    assert orphans == []


def test_get_incomplete(tmp_path):
    """get_incomplete returns list of incomplete alert IDs."""
    cp = ClipCheckpoint(clips_dir=str(tmp_path / "clips"))
    cp.mark_pending("a1")
    cp.mark_pending("a2")
    incomplete = cp.get_incomplete()
    assert sorted(incomplete) == ["a1", "a2"]
