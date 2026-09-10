from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from fusion_server.db.session import init_db
from fusion_server.api import events, alerts, footprint, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
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
        footprint_hash = compute_hash(f"obj_test_001{fake_event.camera_id}{fake_event.timestamp.isoformat()}footprint")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)