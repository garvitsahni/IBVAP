"""
Alerts API - GET /alerts, alert lifecycle management
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio
import uuid

from fusion_server.db.session import get_db
from fusion_server.db.models import Alert
from fusion_server.core.alert_ledger import AlertLedger

from pydantic import BaseModel


class AlertCreate(BaseModel):
    object_id: str
    camera_id: str
    timestamp: datetime
    reason: str
    threat_score: float = 0.0
    clip_path: Optional[str] = None
    trajectory_projection: Optional[dict] = None


class AlertUpdate(BaseModel):
    status: Optional[str] = None  # "fired" | "enriched" | "acknowledged"
    ai_explanation: Optional[str] = None
    clip_path: Optional[str] = None
    trajectory_projection: Optional[dict] = None


class AlertResponse(BaseModel):
    id: int
    alert_id: str
    object_id: str
    camera_id: str
    timestamp: datetime
    reason: str
    status: str
    threat_score: float
    clip_path: Optional[str] = None
    ai_explanation: Optional[str] = None
    trajectory_projection: Optional[dict] = None
    plate_text: Optional[str] = None
    footprint_entry_id: Optional[int] = None
    created_at: datetime
    enriched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    """Create a new alert (fired by rule engine). If clip_path provided, burn-in overlay automatically."""
    alert_id = str(uuid.uuid4())

    # If clip provided, render overlay before persisting
    final_clip_path = alert.clip_path
    if alert.clip_path:
        try:
            from fusion_server.services.clip_overlay import render_overlay
            overlay_out = alert.clip_path.replace(".mp4", "_overlay.mp4")
            render_overlay(
                input_path=alert.clip_path,
                output_path=overlay_out,
                camera_id=alert.camera_id,
                timestamp=alert.timestamp.isoformat(),
                threat_score=alert.threat_score,
                reason=alert.reason,
            )
            final_clip_path = overlay_out
        except Exception:
            pass  # Overlay is best-effort; alert fires regardless (AGENTS.md Rule 4)

    db_alert = Alert(
        alert_id=alert_id,
        object_id=alert.object_id,
        camera_id=alert.camera_id,
        timestamp=alert.timestamp,
        reason=alert.reason,
        status="fired",
        threat_score=alert.threat_score,
        clip_path=final_clip_path,
        trajectory_projection=alert.trajectory_projection,
    )
    db.add(db_alert)

    alert_ledger = AlertLedger()
    alert_ledger.write_alert_with_hash(db, db_alert)

    return AlertResponse(
        id=db_alert.id,
        alert_id=db_alert.alert_id,
        object_id=db_alert.object_id,
        camera_id=db_alert.camera_id,
        timestamp=db_alert.timestamp,
        reason=db_alert.reason,
        status=db_alert.status,
        threat_score=db_alert.threat_score,
        clip_path=db_alert.clip_path,
        ai_explanation=db_alert.ai_explanation,
        trajectory_projection=db_alert.trajectory_projection,
        footprint_entry_id=db_alert.footprint_entry_id,
        created_at=db_alert.created_at,
        enriched_at=db_alert.enriched_at,
    )


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = None,
    object_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List alerts with optional filters."""
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if object_id:
        query = query.filter(Alert.object_id == object_id)
    if camera_id:
        query = query.filter(Alert.camera_id == camera_id)
    if since:
        query = query.filter(Alert.timestamp >= since)
    if until:
        query = query.filter(Alert.timestamp <= until)
    alerts = query.order_by(Alert.timestamp.desc()).offset(offset).limit(limit).all()

    return [
        AlertResponse(
            id=a.id,
            alert_id=a.alert_id,
            object_id=a.object_id,
            camera_id=a.camera_id,
            timestamp=a.timestamp,
            reason=a.reason,
            status=a.status,
            threat_score=a.threat_score,
            clip_path=a.clip_path,
            ai_explanation=a.ai_explanation,
            trajectory_projection=a.trajectory_projection,
            footprint_entry_id=a.footprint_entry_id,
            created_at=a.created_at,
            enriched_at=a.enriched_at,
        )
        for a in alerts
    ]


@router.get("/stream")
async def alert_stream(request: Request):
    """SSE endpoint — streams alert events in real-time."""
    from fusion_server.services.broadcaster import get_broadcaster
    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, db: Session = Depends(get_db)):
    """Get a specific alert by alert_id (UUID)."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse(
        id=alert.id,
        alert_id=alert.alert_id,
        object_id=alert.object_id,
        camera_id=alert.camera_id,
        timestamp=alert.timestamp,
        reason=alert.reason,
        status=alert.status,
        threat_score=alert.threat_score,
        clip_path=alert.clip_path,
        ai_explanation=alert.ai_explanation,
        trajectory_projection=alert.trajectory_projection,
        footprint_entry_id=alert.footprint_entry_id,
        created_at=alert.created_at,
        enriched_at=alert.enriched_at,
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, update: AlertUpdate, db: Session = Depends(get_db)):
    """Update alert (e.g., acknowledge, add AI enrichment)."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if update.status is not None:
        alert.status = update.status
    if update.ai_explanation is not None:
        alert.ai_explanation = update.ai_explanation
        alert.status = "enriched"
        alert.enriched_at = datetime.utcnow()
    if update.clip_path is not None:
        alert.clip_path = update.clip_path
    if update.trajectory_projection is not None:
        alert.trajectory_projection = update.trajectory_projection

    db.commit()
    db.refresh(alert)

    return AlertResponse(
        id=alert.id,
        alert_id=alert.alert_id,
        object_id=alert.object_id,
        camera_id=alert.camera_id,
        timestamp=alert.timestamp,
        reason=alert.reason,
        status=alert.status,
        threat_score=alert.threat_score,
        clip_path=alert.clip_path,
        ai_explanation=alert.ai_explanation,
        trajectory_projection=alert.trajectory_projection,
        footprint_entry_id=alert.footprint_entry_id,
        created_at=alert.created_at,
        enriched_at=alert.enriched_at,
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: str, db: Session = Depends(get_db)):
    """Acknowledge an alert (creates audit trail)."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    db.commit()
    db.refresh(alert)

    return AlertResponse(
        id=alert.id,
        alert_id=alert.alert_id,
        object_id=alert.object_id,
        camera_id=alert.camera_id,
        timestamp=alert.timestamp,
        reason=alert.reason,
        status=alert.status,
        threat_score=alert.threat_score,
        clip_path=alert.clip_path,
        ai_explanation=alert.ai_explanation,
        trajectory_projection=alert.trajectory_projection,
        footprint_entry_id=alert.footprint_entry_id,
        created_at=alert.created_at,
        enriched_at=alert.enriched_at,
    )