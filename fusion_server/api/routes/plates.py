# fusion_server/api/routes/plates.py
"""Plate Detection Query API — Phase 4 ANPR."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from fusion_server.db.session import get_db
from fusion_server.db.models_plate import PlateDetection

from pydantic import BaseModel
from datetime import datetime


class PlateResponse(BaseModel):
    id: int
    object_id: str
    camera_id: str
    plate_text: str
    confidence: float
    bbox: list
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/plates", tags=["plates"])


@router.get("", response_model=List[PlateResponse])
async def list_plates(
    camera_id: Optional[str] = None,
    plate_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List plate detections with optional filters."""
    query = db.query(PlateDetection)
    if camera_id:
        query = query.filter(PlateDetection.camera_id == camera_id)
    if plate_text:
        query = query.filter(PlateDetection.plate_text.ilike(f"%{plate_text}%"))
    return query.order_by(PlateDetection.created_at.desc()).offset(offset).limit(limit).all()
