"""Coverage API — blind-spot computation."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fusion_server.db.session import get_db
from fusion_server.db.models_roi import ROI as ROIModel
from fusion_server.services.camera_health_store import CameraHealthStore
from fusion_server.services.coverage import compute_blind_spots
from fusion_server.core.rule_engine import ROI

router = APIRouter(prefix="/api/v1/coverage", tags=["coverage"])
health_store = CameraHealthStore()


@router.get("/blind-spots")
async def get_blind_spots(db: Session = Depends(get_db)):
    """Compute blind spots for all cameras."""
    all_health = health_store.get_all()
    cameras = [{"camera_id": cid} for cid in all_health.keys()] if all_health else []
    if not cameras:
        cameras = [{"camera_id": "cam1"}, {"camera_id": "cam2"}]

    db_rois = db.query(ROIModel).filter(ROIModel.active == True).all()
    rois = [
        ROI(
            camera_id=r.camera_id, name=r.name, polygon=r.polygon,
            alert_on_enter=r.alert_on_enter, alert_on_exit=r.alert_on_exit,
            object_types=r.object_types,
        )
        for r in db_rois
    ]

    return compute_blind_spots(cameras, rois)
