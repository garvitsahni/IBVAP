"""
Watchlist API - Local encrypted watchlist for face/plate matching
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from fusion_server.db.session import get_db
from fusion_server.db.models import Watchlist

from pydantic import BaseModel, field_validator


class WatchlistCreate(BaseModel):
    watchlist_type: str  # "face" | "plate"
    reference_id: str
    embedding: List[float]
    metadata: Optional[dict] = None
    expires_at: Optional[datetime] = None

    @field_validator("watchlist_type")
    @classmethod
    def validate_watchlist_type(cls, v: str) -> str:
        if v not in ("face", "plate"):
            raise ValueError("watchlist_type must be 'face' or 'plate'")
        return v


class WatchlistUpdate(BaseModel):
    active: Optional[bool] = None
    metadata: Optional[dict] = None
    expires_at: Optional[datetime] = None


class WatchlistResponse(BaseModel):
    id: int
    watchlist_type: str
    reference_id: str
    embedding: List[float]
    metadata: Optional[dict] = None
    active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist_entry(entry: WatchlistCreate, db: Session = Depends(get_db)):
    """Add entry to local watchlist."""
    db_entry = Watchlist(
        watchlist_type=entry.watchlist_type,
        reference_id=entry.reference_id,
        embedding=entry.embedding,
        extra_metadata=entry.metadata,
        active=True,
        expires_at=entry.expires_at,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    return WatchlistResponse(
        id=db_entry.id,
        watchlist_type=db_entry.watchlist_type,
        reference_id=db_entry.reference_id,
        embedding=db_entry.embedding,
        metadata=db_entry.extra_metadata,
        active=db_entry.active,
        created_at=db_entry.created_at,
        expires_at=db_entry.expires_at,
    )


@router.get("", response_model=List[WatchlistResponse])
async def list_watchlist(
    watchlist_type: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List watchlist entries."""
    query = db.query(Watchlist)
    if watchlist_type:
        query = query.filter(Watchlist.watchlist_type == watchlist_type)
    if active_only:
        query = query.filter(Watchlist.active == True)
    entries = query.order_by(Watchlist.created_at.desc()).offset(offset).limit(limit).all()

    return [
        WatchlistResponse(
            id=e.id,
            watchlist_type=e.watchlist_type,
            reference_id=e.reference_id,
            embedding=e.embedding,
            metadata=e.extra_metadata,
            active=e.active,
            created_at=e.created_at,
            expires_at=e.expires_at,
        )
        for e in entries
    ]


@router.get("/{entry_id}", response_model=WatchlistResponse)
async def get_watchlist_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get a specific watchlist entry."""
    entry = db.query(Watchlist).filter(Watchlist.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    return WatchlistResponse(
        id=entry.id,
        watchlist_type=entry.watchlist_type,
        reference_id=entry.reference_id,
        embedding=entry.embedding,
        metadata=entry.metadata,
        active=entry.active,
        created_at=entry.created_at,
        expires_at=entry.expires_at,
    )


@router.patch("/{entry_id}", response_model=WatchlistResponse)
async def update_watchlist_entry(entry_id: int, update: WatchlistUpdate, db: Session = Depends(get_db)):
    """Update watchlist entry."""
    entry = db.query(Watchlist).filter(Watchlist.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    if update.active is not None:
        entry.active = update.active
    if update.metadata is not None:
        entry.extra_metadata = update.metadata
    if update.expires_at is not None:
        entry.expires_at = update.expires_at

    db.commit()
    db.refresh(entry)

    return WatchlistResponse(
        id=entry.id,
        watchlist_type=entry.watchlist_type,
        reference_id=entry.reference_id,
        embedding=entry.embedding,
        metadata=entry.extra_metadata,
        active=entry.active,
        created_at=entry.created_at,
        expires_at=entry.expires_at,
    )


@router.delete("/{entry_id}")
async def delete_watchlist_entry(entry_id: int, db: Session = Depends(get_db)):
    """Delete watchlist entry."""
    entry = db.query(Watchlist).filter(Watchlist.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")

    db.delete(entry)
    db.commit()

    return {"status": "deleted", "entry_id": entry_id}