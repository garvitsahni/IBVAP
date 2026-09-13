"""Ledger API — per-object chain verification status."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import defaultdict

from fusion_server.db.session import get_db
from fusion_server.db.models import FootprintEntry
from fusion_server.core.ledger import compute_hash

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

_last_verified = None
_last_result = None


def _normalize_ts(ts) -> str:
    """Strip timezone info from timestamp for consistent hash computation.

    PostgreSQL returns timezone-aware timestamps (e.g. '...+00:00') even when
    naive timestamps were written. The writer hashes with naive isoformat(),
    so the verifier must do the same to match.
    """
    return ts.replace(tzinfo=None).isoformat()


@router.get("/status")
async def get_ledger_status(db: Session = Depends(get_db)):
    """Verify per-object hash chains. Each object has an independent chain."""
    global _last_verified, _last_result

    entries = db.query(FootprintEntry).order_by(FootprintEntry.id).all()
    total = len(entries)

    if total == 0:
        _last_verified = datetime.utcnow().isoformat()
        _last_result = {"is_valid": True, "broken_at_index": None, "total_entries": 0, "last_verified": _last_verified}
        return _last_result

    # Group entries by object_id, preserve insertion order within each group
    chains = defaultdict(list)
    for entry in entries:
        chains[entry.object_id].append(entry)

    # Global index counter for error reporting
    global_idx = 0
    broken_at = None

    for object_id, chain in chains.items():
        prev_hash = None
        for entry in chain:
            # Recompute expected hash using normalized timestamp (strip tz)
            ts_str = _normalize_ts(entry.timestamp)
            payload = f"{entry.object_id}{entry.camera_id}{ts_str}{entry.event_type}"
            if entry.previous_hash:
                payload += entry.previous_hash
            expected = compute_hash(payload)

            if expected != entry.hash:
                broken_at = global_idx
                break

            # Verify chain linkage: entry's previous_hash should match prior entry's hash
            if prev_hash is not None and entry.previous_hash != prev_hash:
                broken_at = global_idx
                break

            prev_hash = entry.hash
            global_idx += 1

        if broken_at is not None:
            break

    _last_verified = datetime.utcnow().isoformat()
    _last_result = {
        "is_valid": broken_at is None,
        "broken_at_index": broken_at,
        "total_entries": total,
        "last_verified": _last_verified,
    }
    return _last_result
