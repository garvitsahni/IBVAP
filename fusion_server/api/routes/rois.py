"""ROI CRUD API — Phase 4 virtual fence configuration."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fusion_server.db.models_roi import ROI
from fusion_server.db.session import get_db

router = APIRouter(prefix="/api/v1/rois", tags=["rois"])


# ── Request / Response schemas ──────────────────────────────────────────────


class ROICreate(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    polygon: List[List[float]] = Field(..., min_length=3)
    alert_on_enter: bool = True
    alert_on_exit: bool = False
    object_types: Optional[List[str]] = None
    active: bool = True


class ROIUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    polygon: Optional[List[List[float]]] = Field(None, min_length=3)
    alert_on_enter: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    object_types: Optional[List[str]] = None
    active: Optional[bool] = None


class ROIResponse(BaseModel):
    id: UUID
    camera_id: str
    name: str
    polygon: List[List[float]]
    alert_on_enter: bool
    alert_on_exit: bool
    object_types: Optional[List[str]]
    active: bool
    created_at: str

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────


def _roi_to_response(roi: ROI) -> ROIResponse:
    return ROIResponse(
        id=roi.id,
        camera_id=roi.camera_id,
        name=roi.name,
        polygon=roi.polygon,
        alert_on_enter=roi.alert_on_enter,
        alert_on_exit=roi.alert_on_exit,
        object_types=roi.object_types,
        active=roi.active,
        created_at=roi.created_at.isoformat(),
    )


def _get_roi_or_404(roi_id: UUID, db: Session) -> ROI:
    roi = db.query(ROI).filter(ROI.id == roi_id).first()
    if roi is None:
        raise HTTPException(status_code=404, detail="ROI not found")
    return roi


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("", response_model=ROIResponse, status_code=201)
def create_roi(payload: ROICreate, db: Session = Depends(get_db)):
    roi = ROI(**payload.model_dump())
    db.add(roi)
    db.commit()
    db.refresh(roi)
    return _roi_to_response(roi)


@router.get("", response_model=List[ROIResponse])
def list_rois(
    camera_id: Optional[str] = None,
    active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ROI)
    if camera_id is not None:
        query = query.filter(ROI.camera_id == camera_id)
    if active is not None:
        query = query.filter(ROI.active == active)
    return [_roi_to_response(r) for r in query.all()]


@router.get("/{roi_id}", response_model=ROIResponse)
def get_roi(roi_id: UUID, db: Session = Depends(get_db)):
    return _roi_to_response(_get_roi_or_404(roi_id, db))


@router.put("/{roi_id}", response_model=ROIResponse)
def update_roi(roi_id: UUID, payload: ROIUpdate, db: Session = Depends(get_db)):
    roi = _get_roi_or_404(roi_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(roi, key, value)
    db.commit()
    db.refresh(roi)
    return _roi_to_response(roi)


@router.delete("/{roi_id}", status_code=204)
def delete_roi(roi_id: UUID, db: Session = Depends(get_db)):
    roi = _get_roi_or_404(roi_id, db)
    db.delete(roi)
    db.commit()
