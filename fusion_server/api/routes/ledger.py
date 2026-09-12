"""Ledger API — global chain verification status."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fusion_server.db.session import get_db
from fusion_server.db.models import FootprintEntry
from fusion_server.core.ledger import compute_hash

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

_last_verified = None
_last_result = None


@router.get("/status")
async def get_ledger_status(db: Session = Depends(get_db)):
    """Run chain verification and return status."""
    global _last_verified, _last_result

    entries = db.query(FootprintEntry).order_by(FootprintEntry.id).all()
    total = len(entries)

    if total == 0:
        _last_verified = datetime.utcnow().isoformat()
        _last_result = {"is_valid": True, "broken_at_index": None, "total_entries": 0, "last_verified": _last_verified}
        return _last_result

    prev_hash = None
    broken_at = None
    for i, entry in enumerate(entries):
        payload = f"{entry.object_id}{entry.camera_id}{entry.timestamp.isoformat()}{entry.event_type}"
        if prev_hash:
            payload += prev_hash
        expected = compute_hash(payload)
        if expected != entry.hash:
            broken_at = i
            break
        prev_hash = entry.hash

    _last_verified = datetime.utcnow().isoformat()
    _last_result = {
        "is_valid": broken_at is None,
        "broken_at_index": broken_at,
        "total_entries": total,
        "last_verified": _last_verified,
    }
    return _last_result
