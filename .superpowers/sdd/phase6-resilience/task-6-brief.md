# Task 6: Power Manager

**Files:**
- Create: `fusion_server/services/power_manager.py`
- Modify: `requirements.txt` (add psutil)
- Test: `tests/test_power_manager.py`

**Interfaces:**
- Consumes: CPU/memory metrics (via psutil)
- Produces: `PowerManager.get_mode()`, `.check_and_update()`, `.get_affected_cameras()`

## Steps

### Step 1: Add psutil to requirements.txt

Edit `requirements.txt` — add after the existing `opencv-python-headless` line:

```
psutil>=5.9.0
```

### Step 2: Write the failing tests

```python
"""Tests for PowerManager — low-power fallback mode."""
import pytest
from unittest.mock import patch, MagicMock
from fusion_server.services.power_manager import PowerManager


def test_power_manager_initializes_normal():
    """PowerManager starts in 'normal' mode."""
    pm = PowerManager()
    assert pm.get_mode() == "normal"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_reduced(mock_psutil):
    """High CPU triggers 'reduced' mode."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_switches_to_critical(mock_psutil):
    """Very high CPU triggers 'critical' mode."""
    mock_psutil.cpu_percent.return_value = 97.0
    mock_mem = MagicMock()
    mock_mem.percent = 95.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "critical"


@patch("fusion_server.services.power_manager.psutil")
def test_power_manager_recovers(mock_psutil):
    """Low load after reduced triggers recovery to normal."""
    mock_psutil.cpu_percent.return_value = 85.0
    mock_mem = MagicMock()
    mock_mem.percent = 50.0
    mock_psutil.virtual_memory.return_value = mock_mem

    pm = PowerManager()
    pm.check_and_update()
    assert pm.get_mode() == "reduced"

    mock_psutil.cpu_percent.return_value = 30.0
    mock_mem.percent = 50.0
    for _ in range(7):
        pm.check_and_update()
    assert pm.get_mode() == "normal"


def test_camera_priority_by_roi_area():
    """Cameras with larger ROI are higher priority."""
    pm = PowerManager()
    cameras = [
        {"camera_id": "cam1", "roi_area_pct": 10},
        {"camera_id": "cam2", "roi_area_pct": 50},
        {"camera_id": "cam3", "roi_area_pct": 30},
    ]
    affected = pm.get_affected_cameras(cameras, target_count=1)
    assert "cam2" not in affected  # highest priority kept
    assert "cam1" in affected  # lowest priority dropped


def test_mode_callback():
    """Mode change fires callback."""
    cb = MagicMock()
    pm = PowerManager(mode_callback=cb)
    with patch("fusion_server.services.power_manager.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 85.0
        mock_mem = MagicMock()
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem
        pm.check_and_update()
    cb.assert_called_with("normal", "reduced", "cpu_85%")
```

### Step 3: Run tests to verify they fail

Run: `pytest tests/test_power_manager.py -v`
Expected: FAIL

### Step 4: Implement PowerManager

Create `fusion_server/services/power_manager.py`:

```python
"""PowerManager — monitors system load and triggers power-saving modes."""
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None


class PowerManager:
    def __init__(
        self,
        cpu_reduced_threshold: float = 80.0,
        cpu_critical_threshold: float = 95.0,
        mem_free_reduced_pct: float = 20.0,
        mem_free_critical_pct: float = 10.0,
        recovery_threshold: float = 60.0,
        recovery_consecutive: int = 6,
        mode_callback: Optional[Callable] = None,
    ):
        self._cpu_reduced = cpu_reduced_threshold
        self._cpu_critical = cpu_critical_threshold
        self._mem_reduced = mem_free_reduced_pct
        self._mem_critical = mem_free_critical_pct
        self._recovery_threshold = recovery_threshold
        self._recovery_consecutive = recovery_consecutive
        self._mode_callback = mode_callback
        self._mode = "normal"
        self._consecutive_good = 0

    def get_mode(self) -> str:
        return self._mode

    def check_and_update(self):
        if psutil is None:
            return
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        free_pct = 100.0 - mem.percent

        new_mode = self._evaluate(cpu, free_pct)
        if new_mode != self._mode:
            old = self._mode
            reason = self._get_reason(cpu, free_pct)
            self._mode = new_mode
            self._consecutive_good = 0
            logger.warning(f"Power mode: {old} -> {new_mode} ({reason})")
            if self._mode_callback:
                self._mode_callback(old, new_mode, reason)
        elif new_mode != "normal":
            if cpu < self._recovery_threshold and free_pct > self._mem_reduced:
                self._consecutive_good += 1
                if self._consecutive_good >= self._recovery_consecutive:
                    old = self._mode
                    self._mode = "normal"
                    self._consecutive_good = 0
                    logger.info(f"Power recovered: {old} -> normal")
                    if self._mode_callback:
                        self._mode_callback(old, "normal", "load_recovered")
            else:
                self._consecutive_good = 0

    def _evaluate(self, cpu: float, free_pct: float) -> str:
        if cpu > self._cpu_critical or free_pct < self._mem_critical:
            return "critical"
        if cpu > self._cpu_reduced or free_pct < self._mem_reduced:
            return "reduced"
        return "normal"

    def _get_reason(self, cpu: float, free_pct: float) -> str:
        if cpu > self._cpu_critical:
            return f"cpu_{int(cpu)}%"
        if free_pct < self._mem_critical:
            return f"mem_{int(free_pct)}%_free"
        if cpu > self._cpu_reduced:
            return f"cpu_{int(cpu)}%"
        if free_pct < self._mem_reduced:
            return f"mem_{int(free_pct)}%_free"
        return "unknown"

    def get_affected_cameras(self, cameras: List[Dict], target_count: int) -> List[str]:
        sorted_cams = sorted(cameras, key=lambda c: c.get("roi_area_pct", 0), reverse=True)
        keep = sorted_cams[:target_count]
        drop = [c["camera_id"] for c in sorted_cams[target_count:]]
        return drop
```

### Step 5: Install psutil

Run: `pip install psutil>=5.9.0`

### Step 6: Run tests to verify they pass

Run: `pytest tests/test_power_manager.py -v`
Expected: 6 passed

### Step 7: Commit

```bash
git add fusion_server/services/power_manager.py requirements.txt tests/test_power_manager.py
git commit -m "feat: add PowerManager with tiered throttle modes"
```
