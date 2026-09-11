# fusion_server/db/models_roi.py
"""ROI database model — Phase 4."""
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from fusion_server.db.models import Base
import uuid
from datetime import datetime


class ROI(Base):
    __tablename__ = "roi"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(String(64), nullable=False)  # or '*' for all cameras
    name = Column(String(128), nullable=False)
    polygon = Column(JSON, nullable=False)  # [[x, y], ...] normalized 0-1
    alert_on_enter = Column(Boolean, nullable=False, default=True)
    alert_on_exit = Column(Boolean, nullable=False, default=False)
    object_types = Column(JSON, nullable=True)  # ["person", "vehicle"] or None for all
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_roi_camera_active', 'camera_id', 'active'),
    )

    def __init__(self, **kwargs):
        defaults = {
            'alert_on_enter': True,
            'alert_on_exit': False,
            'active': True,
        }
        for key, value in defaults.items():
            kwargs.setdefault(key, value)
        super().__init__(**kwargs)
