import { useState, useEffect } from "react";
import { api } from "../services/api";
import type { DashboardStats } from "../types/api";
import { SystemHealth } from "./SystemHealth";

export function Header() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  useEffect(() => { api.getStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="flex gap-6 items-center text-sm">
      {stats && (
        <>
          <span>Alerts today: <strong>{stats.total_alerts_today}</strong></span>
          <span>Cameras: <strong>{stats.active_cameras}</strong></span>
          <span className="text-alert-critical">Critical: <strong>{stats.alerts_by_severity.critical}</strong></span>
          <span className="text-alert-standard">High: <strong>{stats.alerts_by_severity.high}</strong></span>
          <span>Watchlist: <strong>{stats.active_watchlist_entries}</strong></span>
        </>
      )}
      <SystemHealth />
    </div>
  );
}
