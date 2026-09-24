import type { Alert, FootprintChain, Camera, DashboardStats, LedgerStatus, BlindSpotResult, DetectionEvent } from "../types/api";

const BASE = "/api/v1";

function getAuthToken(): string | null {
  try {
    return localStorage.getItem("ibvap_token");
  } catch {
    return null;
  }
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH", headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export interface CameraCreate {
  camera_id: string; name: string; source_type: string;
  rtsp_url?: string; location?: string; zone?: string;
}

export interface CameraUpdate {
  name?: string; source_type?: string; rtsp_url?: string;
  location?: string; zone?: string; is_active?: boolean;
}

export const api = {
  getAlerts: (params?: string) => get<Alert[]>(`/alerts${params ? `?${params}` : ""}`),
  getAlert: (id: string) => get<Alert>(`/alerts/${id}`),
  acknowledgeAlert: (id: string) => post<Alert>(`/alerts/${id}/acknowledge`),
  escalateAlert: (id: string) => post<Alert>(`/alerts/${id}/escalate`),
  falsePositiveAlert: (id: string) => post<Alert>(`/alerts/${id}/false-positive`),
  alertSnapshotUrl: (id: string) => `${BASE}/alerts/${id}/snapshot`,
  getFootprint: (objectId: string) => get<FootprintChain>(`/footprint/${objectId}`),
  getCameras: () => get<Camera[]>("/cameras"),
  getCameraHealth: () => get<Record<string, unknown>>("/cameras/health"),
  getStats: () => get<DashboardStats>("/dashboard/stats"),
  getLedgerStatus: () => get<LedgerStatus>("/ledger/status"),
  getBlindSpots: () => get<Record<string, BlindSpotResult>>("/coverage/blind-spots"),

  // Camera CRUD
  getCamera: (cameraId: string) => get<Camera>(`/cameras/${cameraId}`),
  createCamera: (data: CameraCreate) => post<Camera>("/cameras", data),
  updateCamera: (cameraId: string, data: CameraUpdate) => patch<Camera>(`/cameras/${cameraId}`, data),
  deleteCamera: (cameraId: string) => del(`/cameras/${cameraId}`),
  seedLocalCamera: () => post<Camera>("/cameras/seed-local"),

  // Detections
  getDetections: (cameraId?: string, limit = 20) =>
    get<DetectionEvent[]>(`/events${cameraId ? `?camera_id=${cameraId}` : ""}${cameraId ? "&" : "?"}limit=${limit}`),

  // Browser webcam detection
  detectFrame: (imageBase64: string, cameraId = "browser-webcam") =>
    post<{ camera_id: string; detections: { bbox: { x1: number; y1: number; x2: number; y2: number }; confidence: number; class_name: string; class_id: number }[]; width: number; height: number; is_dark: boolean }>(
      "/detect",
      { image: imageBase64, camera_id: cameraId, conf_threshold: 0.10 }
    ),
};
