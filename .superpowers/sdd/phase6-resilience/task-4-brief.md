# Task 4: Ledger Checkpoint

**Files:**
- Create: `fusion_server/services/ledger_checkpoint.py`
- Test: `tests/test_ledger_checkpoint.py`

**Interfaces:**
- Consumes: alert_id, hash, chain_length
- Produces: `LedgerCheckpoint.write_checkpoint()`, `.resume()`, `.get_status()`

## Steps

### Step 1: Write the failing tests

```python
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
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_ledger_checkpoint.py -v`
Expected: FAIL

### Step 3: Implement LedgerCheckpoint

Create `fusion_server/services/ledger_checkpoint.py`:

```python
"""LedgerCheckpoint — file-based checkpoint for ledger chain crash recovery."""
import json
import os
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class LedgerCheckpoint:
    def __init__(self, checkpoint_dir: str = "data/checkpoints", max_checkpoints: int = 10):
        self._dir = checkpoint_dir
        self._max = max_checkpoints
        self._last_status: Dict = {"status": "no_checkpoint"}
        os.makedirs(self._dir, exist_ok=True)

    def write_checkpoint(self, alert_id: int, hash: str, chain_length: int):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"ledger_{ts}.json"
        data = {
            "last_alert_id": alert_id,
            "last_hash": hash,
            "chain_length": chain_length,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = os.path.join(self._dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._last_status = {"status": "ok", **data}
        self._prune()
        logger.debug(f"Checkpoint written: {filename}")

    def resume(self) -> Dict:
        files = self._list_checkpoints()
        if not files:
            self._last_status = {"status": "no_checkpoint"}
            return self._last_status
        latest = files[-1]
        with open(os.path.join(self._dir, latest)) as f:
            data = json.load(f)
        self._last_status = {"status": "ok", **data}
        logger.info(f"Resumed from checkpoint: {latest} (alert_id={data['last_alert_id']})")
        return self._last_status

    def get_status(self) -> Dict:
        return dict(self._last_status)

    def _list_checkpoints(self):
        files = [f for f in os.listdir(self._dir) if f.startswith("ledger_") and f.endswith(".json")]
        files.sort()
        return files

    def _prune(self):
        files = self._list_checkpoints()
        while len(files) > self._max:
            os.remove(os.path.join(self._dir, files.pop(0)))
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_ledger_checkpoint.py -v`
Expected: 6 passed

### Step 5: Commit

```bash
git add fusion_server/services/ledger_checkpoint.py tests/test_ledger_checkpoint.py
git commit -m "feat: add LedgerCheckpoint with file-based resume"
```
