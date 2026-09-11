"""
Events API - POST /events from edge nodes
"""
import logging
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from fusion_server.db.session import get_db
from fusion_server.db.models import DetectionEvent
from fusion_server.core.ledger import compute_hash
from fusion_server.services.matching_engine import MatchingEngine
from fusion_server.services.footprint_writer import FootprintChainWriter

logger = logging.getLogger(__name__)

# Pydantic models
from pydantic import BaseModel


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionEventCreate(BaseModel):
    camera_id: str
    timestamp: datetime
    object_type: str  # "person" | "vehicle"
    track_id: str
    bbox: BBox
    embedding: Optional[List[float]] = None
    confidence: float


class DetectionEventResponse(BaseModel):
    id: int
    camera_id: str
    timestamp: datetime
    object_type: str
    object_id: Optional[str] = None
    track_id: str
    bbox: BBox
    embedding: Optional[List[float]] = None
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=DetectionEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event: DetectionEventCreate, db: Session = Depends(get_db)):
    """Receive detection event from edge node."""
    db_event = DetectionEvent(
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        object_type=event.object_type,
        track_id=event.track_id,
        bbox=event.bbox.model_dump(),
        embedding=event.embedding,
        confidence=event.confidence,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    if event.embedding is not None:
        matching_engine = MatchingEngine()
        embedding_array = np.array(event.embedding, dtype=np.float32)
        object_id = matching_engine.match_or_create(
            db=db,
            embedding=embedding_array,
            object_type=event.object_type,
            camera_id=event.camera_id,
            timestamp=event.timestamp,
        )
        db_event.object_id = object_id
        db.commit()
        db.refresh(db_event)

        footprint_writer = FootprintChainWriter()
        footprint_writer.write_entry(
            db=db,
            object_id=object_id,
            camera_id=event.camera_id,
            timestamp=event.timestamp,
            event_type="first_seen",
            detection_event_id=db_event.id,
        )

        # Watchlist matching
        from fusion_server.services.watchlist_matcher import WatchlistMatcher
        from fusion_server.core.alert_ledger import AlertLedger
        from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
        import uuid
        from fusion_server.db.models import Alert

        matcher = WatchlistMatcher()
        match = matcher.match_detection(db, embedding_array, event.object_type)

        if match is not None:
            threat_context = ThreatContext(
                object_type=event.object_type,
                time_of_day="day",  # Default; could be extracted from timestamp
                camera_zone="perimeter",  # Default; could be looked up from camera config
                is_watchlist_match=True,
            )
            score = calculate_threat_score([], threat_context)
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                object_id=object_id,
                camera_id=event.camera_id,
                timestamp=event.timestamp,
                reason="watchlist_match",
                status="fired",
                threat_score=score,
                ai_explanation=f"Matched watchlist entry '{match['reference_id']}' with similarity {match['similarity']}",
            )
            db.add(alert)
            alert_ledger = AlertLedger()
            alert_ledger.write_alert_with_hash(db, alert)

    return DetectionEventResponse(
        id=db_event.id,
        camera_id=db_event.camera_id,
        timestamp=db_event.timestamp,
        object_type=db_event.object_type,
        object_id=db_event.object_id,
        track_id=db_event.track_id,
        bbox=BBox(**db_event.bbox),
        embedding=db_event.embedding,
        confidence=db_event.confidence,
        created_at=db_event.created_at,
    )


@router.get("", response_model=List[DetectionEventResponse])
async def list_events(
    camera_id: Optional[str] = None,
    object_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List detection events with optional filters."""
    query = db.query(DetectionEvent)
    if camera_id:
        query = query.filter(DetectionEvent.camera_id == camera_id)
    if object_type:
        query = query.filter(DetectionEvent.object_type == object_type)
    events = query.order_by(DetectionEvent.timestamp.desc()).offset(offset).limit(limit).all()

    return [
        DetectionEventResponse(
            id=e.id,
            camera_id=e.camera_id,
            timestamp=e.timestamp,
            object_type=e.object_type,
            object_id=e.object_id,
            track_id=e.track_id,
            bbox=BBox(**e.bbox),
            embedding=e.embedding,
            confidence=e.confidence,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/{event_id}", response_model=DetectionEventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    """Get a specific detection event by ID."""
    event = db.query(DetectionEvent).filter(DetectionEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return DetectionEventResponse(
        id=event.id,
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        object_type=event.object_type,
        object_id=event.object_id,
        track_id=event.track_id,
        bbox=BBox(**event.bbox),
        embedding=event.embedding,
        confidence=event.confidence,
        created_at=event.created_at,
    )