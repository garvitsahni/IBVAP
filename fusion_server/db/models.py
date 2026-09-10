from sqlalchemy import (
    Column, BigInteger, String, DateTime, Float, JSON, Text, Boolean, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime

Base = declarative_base()


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    object_type = Column(String(16), nullable=False)  # 'person' | 'vehicle'
    object_id = Column(String(128), nullable=True)  # Global re-ID identity (set by MatchingEngine)
    track_id = Column(String(64), nullable=False)
    bbox = Column(JSON, nullable=False)  # [x1, y1, x2, y2] normalized 0-1
    embedding = Column(Vector(512), nullable=True)  # OSNet/vehicle-ReID embedding
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    footprint_entries = relationship("FootprintEntry", back_populates="detection_event")

    __table_args__ = (
        Index('idx_detection_events_camera_time', 'camera_id', 'timestamp'),
        Index('idx_detection_events_track_id', 'track_id'),
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_detection_confidence'),
        CheckConstraint("object_type IN ('person', 'vehicle')", name='ck_detection_object_type'),
    )


class FootprintEntry(Base):
    __tablename__ = "footprint_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    object_id = Column(String(128), nullable=False)  # Global re-ID matched identity
    camera_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(16), nullable=False)  # 'first_seen' | 'hop' | 'alert' | 'last_seen'
    hash = Column(String(64), nullable=False)  # SHA-256 hex
    previous_hash = Column(String(64), nullable=True)  # NULL for first entry
    detection_event_id = Column(BigInteger, ForeignKey("detection_events.id"), nullable=True)
    alert_id = Column(BigInteger, ForeignKey("alerts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    detection_event = relationship("DetectionEvent", back_populates="footprint_entries")
    alert = relationship("Alert", foreign_keys=[alert_id], remote_side="Alert.id", viewonly=True)

    __table_args__ = (
        Index('idx_footprint_object_time', 'object_id', 'timestamp'),
        Index('idx_footprint_hash', 'hash'),
        Index('idx_footprint_prev_hash', 'previous_hash'),
        CheckConstraint("event_type IN ('first_seen', 'hop', 'alert', 'last_seen')", name='ck_footprint_event_type'),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_id = Column(String(128), nullable=False, unique=True)  # UUID string
    object_id = Column(String(128), nullable=False)
    camera_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(256), nullable=False)  # Deterministic reason from rule engine
    status = Column(String(16), nullable=False, default='fired')  # 'fired' | 'enriched' | 'acknowledged'
    threat_score = Column(Float, nullable=False, default=0.0)
    clip_path = Column(String(512), nullable=True)
    ai_explanation = Column(Text, nullable=True)
    trajectory_projection = Column(JSON, nullable=True)
    footprint_entry_id = Column(BigInteger, ForeignKey("footprint_entries.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    enriched_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    footprint_entry = relationship("FootprintEntry", foreign_keys=[footprint_entry_id], remote_side="FootprintEntry.id", viewonly=True)

    __table_args__ = (
        Index('idx_alerts_object_time', 'object_id', 'timestamp'),
        Index('idx_alerts_status', 'status'),
        Index('idx_alerts_alert_id', 'alert_id'),
        CheckConstraint('threat_score >= 0 AND threat_score <= 1', name='ck_alert_threat_score'),
        CheckConstraint("status IN ('fired', 'enriched', 'acknowledged')", name='ck_alert_status'),
    )


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    watchlist_type = Column(String(16), nullable=False)  # 'face' | 'plate'
    reference_id = Column(String(128), nullable=False)
    embedding = Column(Vector(512), nullable=False)
    extra_metadata = Column("metadata", JSON, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_watchlist_type_active', 'watchlist_type', 'active', postgresql_where=(active == True)),
        CheckConstraint("watchlist_type IN ('face', 'plate')", name='ck_watchlist_type'),
    )