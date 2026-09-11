"""LedgerCheckpoint — file-based checkpoint for ledger chain crash recovery."""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)


class LedgerCheckpoint:
    def __init__(self, checkpoint_dir: str = "data/checkpoints", max_checkpoints: int = 10):
        self._dir = checkpoint_dir
        self._max = max_checkpoints
        self._last_status: Dict = {"status": "no_checkpoint"}
        os.makedirs(self._dir, exist_ok=True)

    def write_checkpoint(self, alert_id: int, hash: str, chain_length: int):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"ledger_{ts}.json"
        data = {
            "last_alert_id": alert_id,
            "last_hash": hash,
            "chain_length": chain_length,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
