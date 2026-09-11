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
