from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from fusion_server.db.session import init_db
from fusion_server.api import events, alerts, footprint, watchlist
from fusion_server.api.routes import cameras, streams, rois, plates, dashboard, ledger, clips, coverage, detect
from fusion_server.api.routes.system import router as system_router, set_aggregator
from fusion_server.services.camera_offline_monitor import CameraOfflineMonitor
from fusion_server.services.detector_fallback import DetectorFallback
from fusion_server.services.ledger_checkpoint import LedgerCheckpoint
from fusion_server.services.clip_checkpoint import ClipCheckpoint
from fusion_server.services.power_manager import PowerManager
from fusion_server.services.resilience_aggregator import ResilienceAggregator

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    # Initialize checkpoint services
    ledger_cp = LedgerCheckpoint()
    clip_cp = ClipCheckpoint()

    # Resume ledger from checkpoint
    ledger_status = ledger_cp.resume()
    logger.info(f"Ledger checkpoint: {ledger_status}")

    # Scan for orphaned clips
    orphans = clip_cp.scan_orphans()
    if orphans:
        logger.warning(f"Found {len(orphans)} orphaned clip(s): {orphans}")

    # Initialize aggregator
    aggregator = ResilienceAggregator()
    aggregator.update_ledger_status(ledger_status.get("status", "ok"))
    set_aggregator(aggregator)

    # Sync registered cameras into the in-memory health store
    from fusion_server.db.session import SessionLocal
    from fusion_server.api.routes.cameras import sync_cameras_to_health_store
    db = SessionLocal()
    try:
        sync_cameras_to_health_store(db)
    except Exception:
        logger.warning("Camera sync failed", exc_info=True)
    finally:
        db.close()

    # Initialize monitors (will be started by their respective owners)
    detector_fallback = DetectorFallback()
    power_manager = PowerManager()

    yield
    # Shutdown (if needed)


app = FastAPI(
    title="IBVAP Fusion Server",
    description="Border Out Post Video Analytics Platform - Fusion Server API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for dashboard/patrol app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(footprint.router)
app.include_router(watchlist.router)
app.include_router(cameras.router)
app.include_router(rois.router)
app.include_router(plates.router)
app.include_router(dashboard.router)
app.include_router(ledger.router)
app.include_router(clips.router)
app.include_router(streams.router)
app.include_router(coverage.router)
app.include_router(detect.router)
app.include_router(system_router)


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard/")


@app.get("/viewer")
async def viewer():
    from fastapi.responses import FileResponse
    return FileResponse("templates/viewer.html")


# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint - verifies API is running."""
    from sqlalchemy import text
    from fusion_server.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    finally:
        db.close()

    from datetime import datetime
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "version": "0.1.0",
    }


# No-op pipeline test endpoint
@app.post("/api/v1/test/noop-pipeline")
async def test_noop_pipeline():
    """
    Test the no-op pipeline: fake detection event → DB → API
    This verifies the Phase 0 exit criteria.
    """
    from sqlalchemy.orm import Session
    from fusion_server.db.session import SessionLocal
    from fusion_server.db.models import DetectionEvent, FootprintEntry, Alert
    from fusion_server.core.ledger import compute_hash
    from datetime import datetime
    import uuid

    db = SessionLocal()
    try:
        # 1. Create fake detection event
        fake_event = DetectionEvent(
            camera_id="cam1",
            timestamp=datetime.utcnow(),
            object_type="person",
            track_id="track_001",
            bbox={"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.8},
            embedding=None,
            confidence=0.95,
        )
        db.add(fake_event)
        db.commit()
        db.refresh(fake_event)

        # 2. Create footprint entry (first_seen)
        footprint_hash = compute_hash(f"obj_test_001{fake_event.camera_id}{fake_event.timestamp.isoformat()}first_seen")
        footprint = FootprintEntry(
            object_id="obj_test_001",
            camera_id=fake_event.camera_id,
            timestamp=fake_event.timestamp,
            event_type="first_seen",
            hash=footprint_hash,
            previous_hash=None,
            detection_event_id=fake_event.id,
        )
        db.add(footprint)
        db.commit()
        db.refresh(footprint)

        # 3. Create alert
        alert_id = str(uuid.uuid4())
        alert = Alert(
            alert_id=alert_id,
            object_id="obj_test_001",
            camera_id=fake_event.camera_id,
            timestamp=datetime.utcnow(),
            reason="virtual_fence_crossing",
            status="fired",
            threat_score=0.7,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        # 4. Link footprint to alert
        alert_footprint_hash = compute_hash(f"{alert.object_id}{alert.camera_id}{alert.timestamp.isoformat()}alert")
        alert_footprint = FootprintEntry(
            object_id=alert.object_id,
            camera_id=alert.camera_id,
            timestamp=alert.timestamp,
            event_type="alert",
            hash=alert_footprint_hash,
            previous_hash=footprint.hash,
            detection_event_id=None,
            alert_id=alert.id,
        )
        db.add(alert_footprint)
        db.commit()

        # 5. Return verification data
        return {
            "status": "success",
            "pipeline": "fake_detection_event → DB → API",
            "detection_event_id": fake_event.id,
            "footprint_entry_id": footprint.id,
            "alert_id": alert.alert_id,
            "alert_status": alert.status,
            "verification": "Run GET /api/v1/alerts and GET /api/v1/footprint/obj_test_001 to verify",
        }
    finally:
        db.close()


# Serve static frontend builds
import os
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to index.html for SPA routing."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, HTTPException) as exc:
            if exc.status_code == 404 and scope["type"] == "http":
                index = os.path.join(self.directory, "index.html")
                if os.path.isfile(index):
                    return FileResponse(index)
            raise


dashboard_build = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.isdir(dashboard_build):
    app.mount("/dashboard", SPAStaticFiles(directory=dashboard_build, html=True), name="dashboard")

patrol_build = os.path.join(os.path.dirname(__file__), "..", "patrol_app", "dist")
if os.path.isdir(patrol_build):
    app.mount("/patrol", SPAStaticFiles(directory=patrol_build, html=True), name="patrol")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)