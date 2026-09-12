# Task 5: Clip Checkpoint

**Files:**
- Create: `fusion_server/services/clip_checkpoint.py`
- Test: `tests/test_clip_checkpoint.py`

**Interfaces:**
- Consumes: alert_id
- Produces: `ClipCheckpoint.mark_pending()`, `.mark_complete()`, `.scan_orphans()`, `.get_incomplete()`

## Steps

### Step 1: Write the failing tests

```python
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
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_clip_checkpoint.py -v`
Expected: FAIL

### Step 3: Implement ClipCheckpoint

Create `fusion_server/services/clip_checkpoint.py`:

```python
"""ClipCheckpoint — tracks in-progress clip renders for crash recovery."""
import os
import logging
from typing import List

logger = logging.getLogger(__name__)


class ClipCheckpoint:
    def __init__(self, clips_dir: str = "data/clips"):
        self._dir = clips_dir
        os.makedirs(self._dir, exist_ok=True)

    def mark_pending(self, alert_id: str):
        path = os.path.join(self._dir, f"{alert_id}.pending")
        with open(path, "w") as f:
            f.write(alert_id)
        logger.debug(f"Clip pending: {alert_id}")

    def mark_complete(self, alert_id: str):
        path = os.path.join(self._dir, f"{alert_id}.pending")
        if os.path.exists(path):
            os.remove(path)
            logger.debug(f"Clip complete: {alert_id}")

    def scan_orphans(self) -> List[str]:
        result = []
        for f in os.listdir(self._dir):
            if f.endswith(".pending"):
                result.append(f.replace(".pending", ""))
        return result

    def get_incomplete(self) -> List[str]:
        return self.scan_orphans()
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_clip_checkpoint.py -v`
Expected: 5 passed

### Step 5: Commit

```bash
git add fusion_server/services/clip_checkpoint.py tests/test_clip_checkpoint.py
git commit -m "feat: add ClipCheckpoint for crash-safe clip rendering"
```
