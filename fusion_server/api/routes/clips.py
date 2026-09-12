"""Clips API — serve alert overlay clips."""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/clips", tags=["clips"])

CLIPS_DIR = os.getenv("CLIPS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "clips"))
os.makedirs(CLIPS_DIR, exist_ok=True)


@router.get("/{filename}")
async def get_clip(filename: str):
    """Serve a clip file."""
    filepath = os.path.join(CLIPS_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(filepath, media_type="video/mp4")
