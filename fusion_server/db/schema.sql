-- IBVAP Frozen Database Schema
-- Matches ARCHITECTURE.md Section 5 Data Contracts exactly
-- DO NOT MODIFY without updating ARCHITECTURE.md and notifying all phase owners

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Table: detection_events
-- Maps to DetectionEvent contract: camera_id, timestamp, object_type, track_id, bbox, embedding, confidence
CREATE TABLE detection_events (
    id BIGSERIAL PRIMARY KEY,
    camera_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    object_type VARCHAR(16) NOT NULL CHECK (object_type IN ('person', 'vehicle')),
    track_id VARCHAR(64) NOT NULL,
    bbox JSONB NOT NULL,  -- [x1, y1, x2, y2] normalized 0-1
    embedding VECTOR(512),  -- OSNet/vehicle-ReID embedding
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_detection_events_camera_time ON detection_events (camera_id, timestamp DESC);
CREATE INDEX idx_detection_events_track_id ON detection_events (track_id);
CREATE INDEX idx_detection_events_embedding ON detection_events USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Table: footprint_entries
-- Maps to FootprintEntry contract: object_id, camera_id, timestamp, event_type, hash, previous_hash
CREATE TABLE footprint_entries (
    id BIGSERIAL PRIMARY KEY,
    object_id VARCHAR(128) NOT NULL,  -- Global re-ID matched identity
    camera_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(16) NOT NULL CHECK (event_type IN ('first_seen', 'hop', 'alert', 'last_seen')),
    hash CHAR(64) NOT NULL,  -- SHA-256 hex
    previous_hash CHAR(64),  -- NULL for first entry in chain
    detection_event_id BIGINT REFERENCES detection_events(id),
    alert_id BIGINT,  -- Will reference alerts table (added after alerts created)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_footprint_object_time ON footprint_entries (object_id, timestamp ASC);
CREATE INDEX idx_footprint_hash ON footprint_entries (hash);
CREATE INDEX idx_footprint_prev_hash ON footprint_entries (previous_hash);

-- Table: alerts
-- Maps to Alert contract: alert_id, object_id, camera_id, timestamp, reason, status, threat_score, clip_path, ai_explanation, trajectory_projection
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(128) NOT NULL UNIQUE,  -- UUID string
    object_id VARCHAR(128) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    reason VARCHAR(256) NOT NULL,  -- Deterministic reason from rule engine
    status VARCHAR(16) NOT NULL DEFAULT 'fired' CHECK (status IN ('fired', 'enriched', 'acknowledged')),
    threat_score DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (threat_score >= 0 AND threat_score <= 1),
    clip_path VARCHAR(512),  -- Path to clip in MinIO/local storage
    ai_explanation TEXT,  -- Async AI enrichment
    trajectory_projection JSONB,  -- Kalman filter projection
    footprint_entry_id BIGINT REFERENCES footprint_entries(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enriched_at TIMESTAMPTZ
);

-- Add foreign key from footprint_entries to alerts (circular reference resolved)
ALTER TABLE footprint_entries
ADD CONSTRAINT fk_footprint_alert
FOREIGN KEY (alert_id) REFERENCES alerts(id);

CREATE INDEX idx_alerts_object_time ON alerts (object_id, timestamp DESC);
CREATE INDEX idx_alerts_status ON alerts (status);
CREATE INDEX idx_alerts_alert_id ON alerts (alert_id);

-- Table: watchlist
-- Local encrypted watchlist for face/plate matching
CREATE TABLE watchlist (
    id BIGSERIAL PRIMARY KEY,
    watchlist_type VARCHAR(16) NOT NULL CHECK (watchlist_type IN ('face', 'plate')),
    reference_id VARCHAR(128) NOT NULL,  -- External reference (e.g., case number)
    embedding VECTOR(512) NOT NULL,  -- Encrypted/stored embedding
    metadata JSONB,  -- Additional info (name, plate_number, etc.)
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_watchlist_type_active ON watchlist (watchlist_type, active) WHERE active = TRUE;
CREATE INDEX idx_watchlist_embedding ON watchlist USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);