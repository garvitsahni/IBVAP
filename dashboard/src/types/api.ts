export interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface DetectionEvent {
  id: number;
  camera_id: string;
  timestamp: string;
  object_type: string;
  object_id: string | null;
  track_id: string;
  bbox: BBox;
  embedding: number[] | null;
  face_embedding: unknown;
  plate_text: string | null;
  confidence: number;
  created_at: string;
}

export interface Alert {
  id: number;
  alert_id: string;
  object_id: string;
  camera_id: string;
  timestamp: string;
  reason: string;
  status: "fired" | "enriched" | "acknowledged";
  threat_score: number;
  clip_path: string | null;
  ai_explanation: string | null;
  trajectory_projection: unknown;
  footprint_entry_id: number | null;
  created_at: string;
  enriched_at: string | null;
}

export interface FootprintEntry {
  id: number;
  object_id: string;
  camera_id: string;
  timestamp: string;
  event_type: string;
  hash: string;
  previous_hash: string | null;
  detection_event: DetectionEventSummary | null;
  created_at: string;
}

export interface FootprintChain {
  object_id: string;
  entries: FootprintEntry[];
  is_valid: boolean;
  first_seen: string | null;
  last_seen: string | null;
  camera_hops: number;
}

export interface DetectionEventSummary {
  id: number;
  camera_id: string;
  timestamp: string;
  object_type: string;
  track_id: string;
  bbox: BBox;
  confidence: number;
}

export interface Camera {
  id: number;
  camera_id: string;
  name: string;
  source_type: string;
  rtsp_url: string | null;
  location: string | null;
  fov_polygon: number[][] | null;
  zone: string | null;
  status: string;
  is_active: boolean;
  last_seen: string;
  health: { ssim: number; metric: number | null };
  created_at: string;
  updated_at: string;
}

export interface CameraListItem {
  camera_id: string;
  name: string;
  source_type: string;
  fov_polygon: number[][];
  status: string;
  is_active: boolean;
  last_seen: string;
  health: { ssim: number; metric: number | null };
}

export interface CameraCreate {
  camera_id: string;
  name: string;
  source_type: string;
  rtsp_url?: string;
  location?: string;
  fov_polygon?: number[][];
  zone?: string;
}

export interface CameraUpdate {
  name?: string;
  source_type?: string;
  rtsp_url?: string;
  location?: string;
  fov_polygon?: number[][];
  zone?: string;
  is_active?: boolean;
}

export interface CameraHealthResponse {
  camera_id: string;
  status: string;
  ssim: number;
  last_updated: string;
  alert_fired: boolean;
  alert_reason: string | null;
}

export interface DashboardStats {
  total_alerts_today: number;
  active_cameras: number;
  alerts_by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  active_watchlist_entries: number;
}

export interface LedgerStatus {
  is_valid: boolean;
  broken_at_index: number | null;
  total_entries: number;
  last_verified: string | null;
}

export interface ROI {
  id: string;
  camera_id: string;
  name: string;
  polygon: number[][];
  alert_on_enter: boolean;
  alert_on_exit: boolean;
  object_types: string[] | null;
  active: boolean;
  created_at: string;
}

export interface ROICreate {
  camera_id: string;
  name: string;
  polygon: number[][];
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  object_types?: string[];
  active?: boolean;
}

export interface ROIUpdate {
  name?: string;
  polygon?: number[][];
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  object_types?: string[];
  active?: boolean;
}

export interface BlindSpotResult {
  fov_polygon: number[][];
  covered_union: number[][][];
  blind_spots: number[][][];
  is_fully_covered: boolean;
}

export interface WatchlistEntry {
  id: number;
  watchlist_type: "face" | "plate";
  reference_id: string;
  embedding: number[];
  metadata: unknown;
  active: boolean;
  created_at: string;
  expires_at: string | null;
}

export interface WatchlistCreate {
  watchlist_type: "face" | "plate";
  reference_id: string;
  embedding: number[];
  metadata?: unknown;
  expires_at?: string;
}

export interface WatchlistUpdate {
  active?: boolean;
  metadata?: unknown;
  expires_at?: string;
}

export interface PlateDetection {
  id: number;
  object_id: string;
  camera_id: string;
  plate_text: string;
  confidence: number;
  bbox: number[];
  created_at: string;
}

export interface DetectionResult {
  bbox: BBox;
  confidence: number;
  class_name: string;
  class_id: number;
}

export interface DetectResponse {
  camera_id: string;
  detections: DetectionResult[];
  width: number;
  height: number;
  is_dark: boolean;
  brightness: number;
  passes: number;
}
