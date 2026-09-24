"""
CooldownGate — deterministic alert dedup (AGENTS.md Rule 1: no ML).

Fires an alert at most once per (camera_id, object_id, reason_key) per
COOLDOWN_SECONDS, and re-arms an ROI key immediately when the object is
observed outside that ROI (update_presence with the current tick's
violating ROI set). Watchlist keys have no ROI presence signal, so they
use the pure 60s time cooldown.

Module-level singleton: AlertPipeline is constructed per request, the
gate must outlive it. Thread-safe (ingestion runs in the threadpool).
"""
import threading
from typing import Dict, Set, Tuple


class CooldownGate:
    COOLDOWN_SECONDS = 60.0

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[Tuple[str, str, str], Dict] = {}

    def should_fire(
        self,
        camera_id: str,
        object_id: str,
        reason_key: str,
        violating: bool,
        now: float,
    ) -> bool:
        key = (camera_id, object_id, reason_key)
        with self._lock:
            st = self._state.get(key)
            if not violating:
                if st is not None:
                    st["active"] = False
                return False
            if st is None:
                self._state[key] = {"active": True, "last_fired": now}
                return True
            fresh = not st["active"]
            if fresh or (now - st["last_fired"] >= self.COOLDOWN_SECONDS):
                st["active"] = True
                st["last_fired"] = now
                return True
            return False

    def update_presence(
        self, camera_id: str, object_id: str, violating_rois: Set[str]
    ) -> None:
        with self._lock:
            for (cam, obj, reason_key), st in self._state.items():
                if cam != camera_id or obj != object_id:
                    continue
                if not reason_key.startswith("roi:"):
                    continue  # watchlist etc. — time-only cooldown
                roi_name = reason_key[len("roi:"):]
                if roi_name not in violating_rois:
                    st["active"] = False

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_GATE = CooldownGate()


def get_cooldown_gate() -> CooldownGate:
    return _GATE
