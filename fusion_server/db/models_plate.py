# fusion_server/db/models_plate.py
"""PlateDetection database model — Phase 4 ANPR."""
from sqlalchemy import Column, String, DateTime, Float, JSON, BigInteger, Index
from fusion_server.db.models import Base
from datetime import datetime


class PlateDetection(Base):
    __tablename__ = "plate_detections"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    object_id = Column(String(128), nullable=False)
    camera_id = Column(String(64), nullable=False)
    plate_text = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    bbox = Column(JSON, nullable=False)  # [x, y, w, h] normalized 0-1
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_plate_camera_time', 'camera_id', 'created_at'),
        Index('idx_plate_text', 'plate_text'),
    )