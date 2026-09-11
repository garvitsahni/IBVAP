"""Tests for LedgerCheckpoint — file-based checkpoint for ledger chain."""
import pytest
import os
import json
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint


def test_checkpoint_creates_dir(tmp_path):
    """write_checkpoint creates checkpoint directory if missing."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "checkpoints"))
    cp.write_checkpoint(alert_id=1, hash="abc123", chain_length=10)
    assert (tmp_path / "checkpoints").exists()


def test_checkpoint_writes_file(tmp_path):
    """write_checkpoint creates a JSON file."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=42, hash="def456", chain_length=156)
    files = os.listdir(str(tmp_path / "cp"))
    assert len(files) == 1
    with open(os.path.join(str(tmp_path / "cp"), files[0])) as f:
        data = json.load(f)
    assert data["last_alert_id"] == 42
    assert data["last_hash"] == "def456"
    assert data["chain_length"] == 156


def test_checkpoint_rolling_window(tmp_path):
    """Only last N checkpoints are kept."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"), max_checkpoints=3)
    for i in range(5):
        cp.write_checkpoint(alert_id=i, hash=f"hash{i}", chain_length=i)
    files = os.listdir(str(tmp_path / "cp"))
    assert len(files) == 3


def test_resume_reads_latest(tmp_path):
    """resume() reads the most recent checkpoint."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=10, hash="hash10", chain_length=10)
    cp.write_checkpoint(alert_id=20, hash="hash20", chain_length=20)
    status = cp.resume()
    assert status["last_alert_id"] == 20
    assert status["last_hash"] == "hash20"
    assert status["chain_length"] == 20


def test_resume_empty_dir(tmp_path):
    """resume() returns empty status when no checkpoints exist."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    status = cp.resume()
    assert status["status"] == "no_checkpoint"


def test_get_status_returns_last(tmp_path):
    """get_status() returns the last checkpoint info."""
    cp = LedgerCheckpoint(checkpoint_dir=str(tmp_path / "cp"))
    cp.write_checkpoint(alert_id=5, hash="h5", chain_length=5)
    status = cp.get_status()
    assert status["status"] == "ok"
    assert status["last_alert_id"] == 5
    assert status["chain_length"] == 5
