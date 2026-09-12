"""Dashboard API — summary stats for the command dashboard."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from fusion_server.db.session import get_db
from fusion_server.db.models import Alert, Watchlist
from fusion_server.services.camera_health_store import CameraHealthStore

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

health_store = CameraHealthStore()


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Return summary stats for the dashboard top bar."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_alerts_today = db.query(func.count(Alert.id)).filter(
        Alert.created_at >= today_start
    ).scalar() or 0

    active_cameras = len(health_store.get_all())

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    recent_alerts = db.query(Alert.threat_score).filter(
        Alert.created_at >= today_start
    ).all()
    for (score,) in recent_alerts:
        if score >= 0.8:
            severity_counts["critical"] += 1
        elif score >= 0.5:
            severity_counts["high"] += 1
        elif score >= 0.3:
            severity_counts["medium"] += 1
        elif score > 0:
            severity_counts["low"] += 1

    active_watchlist = db.query(func.count(Watchlist.id)).filter(
        Watchlist.active == True
    ).scalar() or 0

    return {
        "total_alerts_today": total_alerts_today,
        "active_cameras": active_cameras,
        "alerts_by_severity": severity_counts,
        "active_watchlist_entries": active_watchlist,
    }
