"""
Events API - POST /events from edge nodes
"""
import logging
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, ProgrammingError
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
    face_embedding: Optional[List[float]] = None
    plate_text: Optional[str] = None
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
    face_embedding: Optional[List[float]] = None
    plate_text: Optional[str] = None
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/events", tags=["events"])


EMBEDDING_DIM = 512


@router.post("", response_model=DetectionEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event: DetectionEventCreate, db: Session = Depends(get_db)):
    """Receive detection event from edge node."""
    embedding = event.embedding
    if embedding is not None and len(embedding) != EMBEDDING_DIM:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"embedding must be {EMBEDDING_DIM} dimensions, got {len(embedding)}",
        )

    # Try inserting with new columns; fall back if columns don't exist
    db_event = DetectionEvent(
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        object_type=event.object_type,
        track_id=event.track_id,
        bbox=event.bbox.model_dump(),
        embedding=embedding,
        face_embedding=event.face_embedding,
        plate_text=event.plate_text,
        confidence=event.confidence,
    )
    db.add(db_event)
    try:
        db.commit()
    except (OperationalError, ProgrammingError) as e:
        db.rollback()
        # Columns may not exist yet — check error message, retry without new columns
        err_msg = str(e).lower()
        if "does not exist" in err_msg or "column" in err_msg:
            db_event = DetectionEvent(
                camera_id=event.camera_id,
                timestamp=event.timestamp,
                object_type=event.object_type,
                track_id=event.track_id,
                bbox=event.bbox.model_dump(),
                embedding=embedding,
                confidence=event.confidence,
            )
            db_event.face_embedding = None
            db_event.plate_text = None
            db.add(db_event)
            db.commit()
        else:
            raise  # Re-raise real DB errors
    except Exception:
        db.rollback()
        raise  # Never silently swallow unexpected errors
    db.refresh(db_event)

    object_id = None

    # Body embedding — tracking + footprint
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

    # Watchlist matching — runs if ANY identifying data is present
    from fusion_server.services.watchlist_matcher import WatchlistMatcher
    from fusion_server.core.alert_ledger import AlertLedger
    from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
    import uuid
    from fusion_server.db.models import Alert

    matcher = WatchlistMatcher()
    final_match = None

    # Body embedding matching
    if event.embedding is not None:
        body_match = matcher.match_detection(db, np.array(event.embedding, dtype=np.float32), event.object_type)
        if body_match:
            final_match = body_match

    # Face-specific matching (independent of body embedding)
    if event.face_embedding is not None and event.object_type == "person":
        face_emb_array = np.array(event.face_embedding, dtype=np.float32)
        face_match = matcher.match_face(db, face_emb_array)
        if face_match and (final_match is None or face_match["similarity"] > final_match["similarity"]):
            final_match = face_match

    # Plate text matching (independent of body embedding)
    if event.plate_text is not None and event.object_type == "vehicle":
        plate_match = matcher.match_plate_text(db, event.plate_text)
        if plate_match and (final_match is None or plate_match["similarity"] > final_match["similarity"]):
            final_match = plate_match

    # Fire watchlist alert
    if final_match is not None:
        threat_context = ThreatContext(
            object_type=event.object_type,
            time_of_day="day",
            camera_zone="perimeter",
            is_watchlist_match=True,
        )
        score = calculate_threat_score([], threat_context)
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            object_id=object_id or f"unknown-{db_event.id}",
            camera_id=event.camera_id,
            timestamp=event.timestamp,
            reason="watchlist_match",
            status="fired",
            threat_score=score,
            plate_text=event.plate_text,
            ai_explanation=f"Matched watchlist entry '{final_match['reference_id']}' with similarity {final_match['similarity']}",
        )
        db.add(alert)
        alert_ledger = AlertLedger()
        alert_ledger.write_alert_with_hash(db, alert)

    # Alert pipeline: rule engine, trajectory, suspicious activity, threat scoring
    if object_id is not None:
        from fusion_server.services.alert_pipeline import AlertPipeline
        from fusion_server.services.ai_enrichment import AIEnrichmentService
        from fusion_server.services.broadcaster import get_broadcaster

        enrichment_service = AIEnrichmentService()
        broadcaster = get_broadcaster()
        pipeline = AlertPipeline(db=db, enrichment_service=enrichment_service)
        pipeline.set_sse_broadcaster(broadcaster)
        pipeline.process({
            "camera_id": event.camera_id,
            "object_id": object_id,
            "object_type": event.object_type,
            "timestamp": event.timestamp,
            "track_id": event.track_id,
            "bbox": event.bbox.model_dump(),
            "confidence": event.confidence,
        })

    # Broadcast detection to SSE subscribers (non-blocking)
    from fusion_server.services.broadcaster import get_broadcaster
    try:
        broadcaster = get_broadcaster()
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcaster.broadcast_detection({
                "camera_id": db_event.camera_id,
                "object_type": db_event.object_type,
                "object_id": db_event.object_id,
                "track_id": db_event.track_id,
                "bbox": db_event.bbox,
                "confidence": db_event.confidence,
                "timestamp": db_event.timestamp.isoformat() if hasattr(db_event.timestamp, 'isoformat') else str(db_event.timestamp),
            }))
    except Exception:
        pass  # Never block event delivery on broadcast failure

    return DetectionEventResponse(
        id=db_event.id,
        camera_id=db_event.camera_id,
        timestamp=db_event.timestamp,
        object_type=db_event.object_type,
        object_id=db_event.object_id,
        track_id=db_event.track_id,
        bbox=BBox(**db_event.bbox),
        embedding=db_event.embedding,
        face_embedding=db_event.face_embedding,
        plate_text=db_event.plate_text,
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
            face_embedding=e.face_embedding,
            plate_text=e.plate_text,
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
        face_embedding=event.face_embedding,
        plate_text=event.plate_text,
        confidence=event.confidence,
        created_at=event.created_at,
    )