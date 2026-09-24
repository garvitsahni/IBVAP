export interface BBox { x1: number; y1: number; x2: number; y2: number }

export interface DetectionEvent {
  id: number; camera_id: string; timestamp: string; object_type: string;
  object_id: string | null; track_id: string; bbox: BBox;
  embedding: number[] | null; confidence: number; created_at: string;
}

export type AlertStatus = "fired" | "enriched" | "acknowledged" | "escalated" | "false_positive";
export type ThreatLevel = "critical" | "high" | "medium" | "low" | "none";

export interface Alert {
  id: number; alert_id: string; object_id: string; camera_id: string;
  timestamp: string; reason: string; status: AlertStatus;
  threat_score: number; threat_level?: ThreatLevel | null;
  clip_path: string | null; ai_explanation: string | null;
  ai_source: string | null;
  trajectory_projection: Record<string, unknown> | null;
  plate_text: string | null; reason_detail: string | null;
  snapshot_path: string | null;
  footprint_entry_id: number | null; created_at: string; enriched_at: string | null;
}

export interface FootprintEntry {
  id: number; object_id: string; camera_id: string; timestamp: string;
  event_type: string; hash: string; previous_hash: string | null;
  detection_event: DetectionEvent | null; created_at: string;
}

export interface FootprintChain {
  object_id: string; entries: FootprintEntry[];
  is_valid: boolean; first_seen: string | null;
  last_seen: string | null; camera_hops: number;
}

export interface Camera {
  camera_id: string; name: string; fov_polygon: number[][];
  status: string; last_seen: string; health: { ssim: number; metric: number };
}

export interface CameraHealthEntry {
  status: string;
  last_seen?: string;
  last_updated?: string;
  ssim?: number;
  metric?: number;
  reduced_accuracy_mode?: boolean;
  detect_p95_ms?: number;
}

export interface SystemHealth {
  status: string;
  cameras: Record<string, string>;
  coverage_gaps: unknown[];
  detection_tier: string;
  ledger: { status: string };
  power_mode: string;
}

export interface DashboardStats {
  total_alerts_today: number; active_cameras: number;
  alerts_by_severity: { critical: number; high: number; medium: number; low: number };
  active_watchlist_entries: number;
}

export interface LedgerStatus {
  is_valid: boolean; broken_at_index: number | null;
  total_entries: number; last_verified: string | null;
}

export interface BlindSpotResult {
  fov_polygon: number[][]; covered_union: number[][][];
  blind_spots: number[][][]; is_fully_covered: boolean;
}
