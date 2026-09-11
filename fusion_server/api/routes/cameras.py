"""
Cameras API - GET /cameras/health for camera health status,
POST /cameras/{camera_id}/health to update status and fire alerts.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fusion_server.db.session import get_db
from fusion_server.services.camera_health_store import CameraHealthStore

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

# Module-level singleton for the in-memory camera health store
health_store = CameraHealthStore()


class CameraHealthRequest(BaseModel):
    status: str  # "ok" | "blinding" | "obscured" | "frozen" | "tamper" | "drift"
    ssim: float
    metric: Optional[float] = None


class CameraHealthResponse(BaseModel):
    camera_id: str
    status: str
    ssim: float
    last_updated: str
    alert_fired: bool = False
    alert_reason: Optional[str] = None


class CameraListItem(BaseModel):
    camera_id: str
    name: str
    fov_polygon: list = []
    status: str
    last_seen: str = ""
    health: dict = {}


@router.get("")
async def list_cameras():
    """List all known cameras with health status."""
    all_health = health_store.get_all()
    cameras = []
    for camera_id, info in all_health.items():
        cameras.append(CameraListItem(
            camera_id=camera_id,
            name=camera_id,
            fov_polygon=[],
            status=info.get("status", "ok"),
            last_seen=info.get("last_updated", ""),
            health={"ssim": info.get("ssim", 0), "metric": info.get("metric")},
        ))
    return cameras


@router.get("/health")
async def get_camera_health() -> Dict[str, Dict[str, Any]]:
    """Get health status for all cameras."""
    return health_store.get_all()


@router.post("/{camera_id}/health", response_model=CameraHealthResponse)
async def update_camera_health(
    camera_id: str,
    request: CameraHealthRequest,
    db: Session = Depends(get_db),
):
    """Update camera health status. Fires alert if status is not 'ok'."""
    health_store.update(camera_id, {
        "status": request.status,
        "ssim": request.ssim,
        "metric": request.metric,
    })

    alert_fired = False
    alert_reason = None

    if request.status != "ok":
        from fusion_server.db.models import Alert
        from fusion_server.core.alert_ledger import AlertLedger
        from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
        from fusion_server.core.rule_engine import RuleViolation

        alert_reason = f"camera_{request.status}"
        
        # Map camera status to violation type
        violation_type_map = {
            "blinding": "camera_blinding",
            "obscured": "camera_tamper",
            "frozen": "camera_frozen",
            "tamper": "camera_tamper",
            "drift": "camera_drift",
        }
        violation_type = violation_type_map.get(request.status, "camera_tamper")
        
        violation = RuleViolation(
            object_id=f"camera_{camera_id}",
            camera_id=camera_id,
            timestamp=datetime.utcnow().isoformat(),
            roi_name="N/A",
            violation_type=violation_type,
            threat_score=0.0,  # Will be calculated
        )
        
        threat_context = ThreatContext(
            object_type="vehicle",  # Camera is infrastructure, use vehicle as default
            time_of_day="day",  # Default; could be extracted from timestamp
            camera_zone="perimeter",  # Default; could be looked up from camera config
        )
        
        score = calculate_threat_score([violation], threat_context)
        
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            object_id=f"camera_{camera_id}",
            camera_id=camera_id,
            timestamp=datetime.utcnow(),
            reason=alert_reason,
            status="fired",
            threat_score=score,
        )
        db.add(alert)
        alert_ledger = AlertLedger()
        alert_ledger.write_alert_with_hash(db, alert)
        alert_fired = True

    return CameraHealthResponse(
        camera_id=camera_id,
        status=request.status,
        ssim=request.ssim,
        last_updated=health_store.get(camera_id).get("last_updated", ""),
        alert_fired=alert_fired,
        alert_reason=alert_reason,
    )


@router.post("/{camera_id}/heartbeat")
async def camera_heartbeat(camera_id: str):
    """Record a heartbeat from an edge worker."""
    health_store.heartbeat(camera_id)
    return {"camera_id": camera_id, "status": "ok"}
