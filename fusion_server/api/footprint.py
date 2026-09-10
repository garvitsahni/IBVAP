"""
Footprint API - GET /footprint/{object_id} for cross-camera tracking chain
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from fusion_server.db.session import get_db
from fusion_server.db.models import FootprintEntry, DetectionEvent

from pydantic import BaseModel


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionEventSummary(BaseModel):
    id: int
    camera_id: str
    timestamp: datetime
    object_type: str
    track_id: str
    bbox: BBox
    confidence: float

    class Config:
        from_attributes = True


class FootprintEntryResponse(BaseModel):
    id: int
    object_id: str
    camera_id: str
    timestamp: datetime
    event_type: str
    hash: str
    previous_hash: Optional[str] = None
    detection_event: Optional[DetectionEventSummary] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FootprintChainResponse(BaseModel):
    object_id: str
    entries: List[FootprintEntryResponse]
    is_valid: bool
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    camera_hops: int = 0


router = APIRouter(prefix="/api/v1/footprint", tags=["footprint"])


@router.get("/{object_id}", response_model=FootprintChainResponse)
async def get_footprint_chain(object_id: str, db: Session = Depends(get_db)):
    """
    Get full footprint chain for an object (ordered by timestamp).
    Includes chain verification and summary stats.
    """
    entries = (
        db.query(FootprintEntry)
        .filter(FootprintEntry.object_id == object_id)
        .order_by(FootprintEntry.timestamp.asc())
        .all()
    )

    if not entries:
        raise HTTPException(status_code=404, detail="Footprint chain not found")

    # Verify chain integrity
    from fusion_server.core.ledger import verify_chain
    chain_data = [
        {
            "object_id": e.object_id,
            "camera_id": e.camera_id,
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "hash": e.hash,
            "previous_hash": e.previous_hash,
        }
        for e in entries
    ]
    is_valid, broken_idx = verify_chain(chain_data)

    # Build response with detection event details
    entry_responses = []
    for entry in entries:
        det_event = None
        if entry.detection_event_id:
            det = db.query(DetectionEvent).filter(DetectionEvent.id == entry.detection_event_id).first()
            if det:
                det_event = DetectionEventSummary(
                    id=det.id,
                    camera_id=det.camera_id,
                    timestamp=det.timestamp,
                    object_type=det.object_type,
                    track_id=det.track_id,
                    bbox=BBox(**det.bbox),
                    confidence=det.confidence,
                )

        entry_responses.append(FootprintEntryResponse(
            id=entry.id,
            object_id=entry.object_id,
            camera_id=entry.camera_id,
            timestamp=entry.timestamp,
            event_type=entry.event_type,
            hash=entry.hash,
            previous_hash=entry.previous_hash,
            detection_event=det_event,
            created_at=entry.created_at,
        ))

    # Summary stats
    first_seen = entries[0].timestamp if entries else None
    last_seen = entries[-1].timestamp if entries else None
    camera_hops = len(set(e.camera_id for e in entries)) - 1 if len(entries) > 1 else 0

    return FootprintChainResponse(
        object_id=object_id,
        entries=entry_responses,
        is_valid=is_valid,
        first_seen=first_seen,
        last_seen=last_seen,
        camera_hops=camera_hops,
    )


@router.get("/{object_id}/verify")
async def verify_footprint_chain(object_id: str, db: Session = Depends(get_db)):
    """Verify hash chain integrity for a footprint."""
    entries = (
        db.query(FootprintEntry)
        .filter(FootprintEntry.object_id == object_id)
        .order_by(FootprintEntry.timestamp.asc())
        .all()
    )

    if not entries:
        raise HTTPException(status_code=404, detail="Footprint chain not found")

    from fusion_server.core.ledger import verify_chain
    chain_data = [
        {
            "object_id": e.object_id,
            "camera_id": e.camera_id,
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "hash": e.hash,
            "previous_hash": e.previous_hash,
        }
        for e in entries
    ]
    is_valid, broken_idx = verify_chain(chain_data)

    return {
        "object_id": object_id,
        "is_valid": is_valid,
        "total_entries": len(entries),
        "broken_at_index": broken_idx,
        "broken_entry": chain_data[broken_idx] if broken_idx is not None else None,
    }