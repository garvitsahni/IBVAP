import type { Alert, FootprintChain, Camera, DashboardStats, LedgerStatus, BlindSpotResult } from "../types/api";

const BASE = "/api/v1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  getDeviceId: () => {
    let id = localStorage.getItem("ibvap_device_id");
    if (!id) {
      id = `patrol-${Math.random().toString(36).slice(2, 6)}`;
      localStorage.setItem("ibvap_device_id", id);
    }
    return id;
  },
  getAlerts: (params?: string) => get<Alert[]>(`/alerts${params ? `?${params}` : ""}`),
  getAlert: (id: string) => get<Alert>(`/alerts/${id}`),
  acknowledgeAlert: (id: string) => post<Alert>(`/alerts/${id}/acknowledge`),
  getFootprint: (objectId: string) => get<FootprintChain>(`/footprint/${objectId}`),
  getCameras: () => get<Camera[]>("/cameras"),
  getCameraHealth: () => get<Record<string, unknown>>("/cameras/health"),
  getStats: () => get<DashboardStats>("/dashboard/stats"),
  getLedgerStatus: () => get<LedgerStatus>("/ledger/status"),
  getBlindSpots: () => get<Record<string, BlindSpotResult>>("/coverage/blind-spots"),
};
