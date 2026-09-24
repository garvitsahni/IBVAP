import type { Alert } from "@/types/api";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface FeedAlert {
  id: string;
  type: string;
  severity: Severity;
  cameraId: string;
  timestamp: string;
  status: string;
  plateText: string | null;
  reasonDetail: string | null;
  threatScore: number;
  snapshotPath: string | null;
  aiExplanation: string | null;
  aiSource: string | null;
}

export const REASON_LABELS: Record<string, string> = {
  roi_intrusion: "ROI Intrusion",
  virtual_fence_crossing: "Virtual Fence Crossing",
  watchlist_match: "Watchlist Match",
  camera_dark: "Camera Dark",
  camera_blur: "Camera Blur",
  camera_frozen: "Camera Frozen",
  camera_blinding: "Camera Blinding",
  camera_obscured: "Camera Obscured",
};

export function labelForReason(reason: string): string {
  return REASON_LABELS[reason] ?? reason.replace(/_/g, " ");
}

export function mapSeverity(threatScore: number): Severity {
  if (threatScore >= 0.8) return "critical";
  if (threatScore >= 0.6) return "high";
  if (threatScore >= 0.4) return "medium";
  if (threatScore >= 0.2) return "low";
  return "info";
}

export function mapApiAlert(raw: Alert): FeedAlert {
  return {
    id: raw.alert_id || String(raw.id),
    type: labelForReason(raw.reason),
    severity: mapSeverity(raw.threat_score),
    cameraId: raw.camera_id,
    timestamp: raw.timestamp,
    status: raw.status ?? "fired",
    plateText: raw.plate_text || null,
    reasonDetail: raw.reason_detail || null,
    threatScore: raw.threat_score,
    snapshotPath: raw.snapshot_path || null,
    aiExplanation: raw.ai_explanation || null,
    aiSource: raw.ai_source || null,
  };
}

export function isOpenStatus(status: string): boolean {
  return status === "fired" || status === "enriched";
}
