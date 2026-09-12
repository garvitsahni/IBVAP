"""Streams API — HLS video stream endpoints."""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/streams", tags=["streams"])

HLS_DIR = os.getenv("HLS_DIR", "/tmp/ibvap_hls")


@router.get("/{camera_id}.m3u8")
async def get_hls_playlist(camera_id: str):
    """Serve HLS playlist for a camera."""
    playlist = os.path.join(HLS_DIR, camera_id, "stream.m3u8")
    if not os.path.isfile(playlist):
        raise HTTPException(status_code=404, detail="Stream not available")
    return FileResponse(playlist, media_type="application/x-mpegurl")


@router.get("/{camera_id}/{segment}.ts")
async def get_hls_segment(camera_id: str, segment: str):
    """Serve HLS segment for a camera."""
    seg_path = os.path.join(HLS_DIR, camera_id, f"{segment}.ts")
    if not os.path.isfile(seg_path):
        raise HTTPException(status_code=404, detail="Segment not found")
    return FileResponse(seg_path, media_type="video/mp2t")
