"""
Cameras API - GET /cameras/health for camera health status.
"""
from fastapi import APIRouter
from typing import Dict, Any

from fusion_server.services.camera_health_store import CameraHealthStore

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

# Module-level singleton for the in-memory camera health store
health_store = CameraHealthStore()


@router.get("/health")
async def get_camera_health() -> Dict[str, Dict[str, Any]]:
    """Get health status for all cameras."""
    return health_store.get_all()
