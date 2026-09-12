import { useState, useEffect } from "react";
import { AlertTriangle, Camera, Eye, BookMarked } from "lucide-react";
import { api } from "../services/api";
import type { DashboardStats } from "../types/api";

export function SidebarStats() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  const items = [
    { label: "Alerts", value: stats.total_alerts_today, icon: AlertTriangle, color: "text-severity-high" },
    { label: "Cameras", value: stats.active_cameras, icon: Camera, color: "text-status-ok" },
    { label: "Critical", value: stats.alerts_by_severity.critical, icon: Eye, color: "text-severity-critical" },
    { label: "Watchlist", value: stats.active_watchlist_entries, icon: BookMarked, color: "text-accent" },
  ];

  return (
    <div className="flex items-center gap-6">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="flex items-center gap-2">
            <Icon className={`w-3.5 h-3.5 ${item.color}`} strokeWidth={1.5} />
            <span className="text-[11px] text-text-muted font-medium tracking-wide">{item.label}</span>
            <span className="text-[11px] font-semibold text-text-primary tabular-nums">{item.value}</span>
          </div>
        );
      })}
    </div>
  );
}
