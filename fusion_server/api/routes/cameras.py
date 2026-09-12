"""
Cameras API — Full CRUD + health monitoring + seed endpoint.
Static routes MUST be defined before parameterized routes.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fusion_server.db.session import get_db
from fusion_server.db.models import Camera
from fusion_server.services.camera_health_store import CameraHealthStore

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

# Module-level singleton for the in-memory camera health store
health_store = CameraHealthStore()


# ── Pydantic Schemas ──────────────────────────────────────────────────────


class CameraCreate(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    source_type: str = Field(default="unknown", pattern="^(rtsp|usb|webcam|hls|unknown)$")
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    fov_polygon: Optional[List[List[float]]] = None
    zone: Optional[str] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    source_type: Optional[str] = Field(None, pattern="^(rtsp|usb|webcam|hls|unknown)$")
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    fov_polygon: Optional[List[List[float]]] = None
    zone: Optional[str] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    id: int
    camera_id: str
    name: str
    source_type: str
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    fov_polygon: Optional[List[List[float]]] = None
    zone: Optional[str] = None
    status: str
    is_active: bool
    last_seen: str = ""
    health: dict = {}
    created_at: str
    updated_at: str


class CameraHealthRequest(BaseModel):
    status: str
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
    source_type: str = "unknown"
    fov_polygon: list = []
    status: str
    is_active: bool = True
    last_seen: str = ""
    health: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────


def _camera_to_response(cam: Camera, health_info: dict = None) -> CameraResponse:
    """Convert a DB Camera model to a response schema."""
    h = health_info or health_store.get(cam.camera_id)
    last_seen_raw = h.get("last_updated", h.get("last_seen", ""))
    if isinstance(last_seen_raw, datetime):
        last_seen_raw = last_seen_raw.isoformat()
    return CameraResponse(
        id=cam.id,
        camera_id=cam.camera_id,
        name=cam.name,
        source_type=cam.source_type,
        rtsp_url=cam.rtsp_url,
        location=cam.location,
        fov_polygon=cam.fov_polygon or [],
        zone=cam.zone,
        status=h.get("status", cam.status),
        is_active=cam.is_active,
        last_seen=last_seen_raw,
        health={"ssim": h.get("ssim", 0), "metric": h.get("metric")},
        created_at=cam.created_at.isoformat() if cam.created_at else "",
        updated_at=cam.updated_at.isoformat() if cam.updated_at else "",
    )


# ── Static Routes (MUST come before /{camera_id}) ────────────────────────


@router.get("/health")
async def get_camera_health() -> Dict[str, Dict[str, Any]]:
    """Get health status for all cameras."""
    return health_store.get_all()


@router.post("/seed-local", response_model=CameraResponse, status_code=201)
async def seed_local_camera(db: Session = Depends(get_db)):
    """Register the laptop webcam as a local camera if not already registered."""
    camera_id = "laptop-webcam"
    try:
        existing = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    except Exception:
        existing = None
    if existing:
        return _camera_to_response(existing)

    cam = Camera(
        camera_id=camera_id,
        name="Laptop Camera",
        source_type="webcam",
        status="registered",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return _camera_to_response(cam)


# ── CRUD Endpoints ─────────────────────────────────────────────────────────


@router.get("", response_model=List[CameraListItem])
async def list_cameras(db: Session = Depends(get_db)):
    """List all registered cameras, merged with live health data."""
    try:
        db_cameras = db.query(Camera).filter(Camera.is_active == True).all()
    except Exception:
        db_cameras = []  # cameras table may not exist yet
    all_health = health_store.get_all()

    cameras = []
    for cam in db_cameras:
        h = all_health.get(cam.camera_id, {})
        last_seen_raw = h.get("last_updated", h.get("last_seen", ""))
        if isinstance(last_seen_raw, datetime):
            last_seen_raw = last_seen_raw.isoformat()
        cameras.append(CameraListItem(
            camera_id=cam.camera_id,
            name=cam.name,
            source_type=cam.source_type,
            fov_polygon=cam.fov_polygon or [],
            status=h.get("status", cam.status),
            is_active=cam.is_active,
            last_seen=last_seen_raw,
            health={"ssim": h.get("ssim", 0), "metric": h.get("metric")},
        ))

    # Include cameras that are in health store but not in DB (edge-registered)
    db_ids = {c.camera_id for c in db_cameras}
    for camera_id, info in all_health.items():
        if camera_id not in db_ids:
            cameras.append(CameraListItem(
                camera_id=camera_id,
                name=camera_id,
                source_type="unknown",
                fov_polygon=[],
                status=info.get("status", "ok"),
                is_active=True,
                last_seen=info.get("last_updated", ""),
                health={"ssim": info.get("ssim", 0), "metric": info.get("metric")},
            ))

    return cameras


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(data: CameraCreate, db: Session = Depends(get_db)):
    """Register a new camera."""
    try:
        existing = db.query(Camera).filter(Camera.camera_id == data.camera_id).first()
    except Exception:
        existing = None
    if existing:
        raise HTTPException(status_code=409, detail=f"Camera '{data.camera_id}' already exists")

    cam = Camera(
        camera_id=data.camera_id,
        name=data.name,
        source_type=data.source_type,
        rtsp_url=data.rtsp_url,
        location=data.location,
        fov_polygon=data.fov_polygon,
        zone=data.zone,
        status="registered",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return _camera_to_response(cam)


# ── Parameterized Routes (MUST come AFTER static routes) ──────────────────


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Get a single camera by ID."""
    try:
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    except Exception:
        cam = None
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    return _camera_to_response(cam)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, data: CameraUpdate, db: Session = Depends(get_db)):
    """Update camera configuration."""
    try:
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    except Exception:
        cam = None
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cam, field, value)
    cam.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(cam)
    return _camera_to_response(cam)


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    """Remove a camera registration."""
    try:
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    except Exception:
        cam = None
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

    db.delete(cam)
    db.commit()


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

    # Update DB camera status if it exists (graceful if table missing)
    try:
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        if cam:
            cam.status = request.status if request.status == "ok" else "error"
            cam.updated_at = datetime.utcnow()
            db.commit()
    except Exception:
        pass  # cameras table may not exist yet

    alert_fired = False
    alert_reason = None

    if request.status != "ok":
        from fusion_server.db.models import Alert
        from fusion_server.core.alert_ledger import AlertLedger
        from fusion_server.core.threat_scoring import calculate_threat_score, ThreatContext
        from fusion_server.core.rule_engine import RuleViolation

        alert_reason = f"camera_{request.status}"

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
            threat_score=0.0,
        )

        threat_context = ThreatContext(
            object_type="vehicle",
            time_of_day="day",
            camera_zone="perimeter",
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


# ── Startup Sync ───────────────────────────────────────────────────────────


def sync_cameras_to_health_store(db: Session):
    """Load all active DB cameras into the in-memory health store on startup."""
    cameras = db.query(Camera).filter(Camera.is_active == True).all()
    for cam in cameras:
        if health_store.get(cam.camera_id).get("status") == "unknown":
            health_store.heartbeat(cam.camera_id)
