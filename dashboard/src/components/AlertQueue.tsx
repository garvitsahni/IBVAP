import { useState, useEffect, useRef } from "react";
import { api } from "../services/api";
import { SSEClient } from "../services/sse";
import type { Alert } from "../types/api";
import { AlertCard } from "./AlertCard";
import { AlertTriangle, Filter } from "lucide-react";

export function AlertQueue({ onSelectAlert }: { onSelectAlert: (alert: Alert) => void }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;

  useEffect(() => {
    api.getAlerts("limit=50").then(setAlerts).catch(console.error);
  }, []);

  // SSE for real-time alert updates
  useEffect(() => {
    const client = new SSEClient();
    client.connect("/api/v1/alerts/stream");

    client.on("alert_fired", (data) => {
      const newAlert: Alert = {
        id: 0,
        alert_id: data.alert_id as string,
        object_id: data.object_id as string,
        camera_id: data.camera_id as string,
        timestamp: data.timestamp as string,
        reason: data.reason as string,
        status: "fired",
        threat_score: data.threat_score as number,
        clip_path: null,
        ai_explanation: null,
        trajectory_projection: null,
        footprint_entry_id: null,
        created_at: new Date().toISOString(),
        enriched_at: null,
      };
      setAlerts((prev) => {
        if (prev.some((a) => a.alert_id === newAlert.alert_id)) return prev;
        return [newAlert, ...prev].slice(0, 100);
      });
    });

    client.on("alert_enriched", (data) => {
      setAlerts((prev) =>
        prev.map((a) =>
          a.alert_id === data.alert_id
            ? { ...a, status: "enriched" as const, ai_explanation: data.ai_explanation as string }
            : a
        )
      );
    });

    return () => {
      client.disconnect();
    };
  }, []);

  const sorted = [...alerts]
    .filter((a) => {
      if (severityFilter === "all") return true;
      if (severityFilter === "critical") return a.threat_score >= 0.8;
      if (severityFilter === "high") return a.threat_score >= 0.5 && a.threat_score < 0.8;
      if (severityFilter === "acknowledged") return a.status === "acknowledged";
      return true;
    })
    .sort((a, b) => {
      if (a.status === "acknowledged" && b.status !== "acknowledged") return 1;
      if (a.status !== "acknowledged" && b.status === "acknowledged") return -1;
      return b.threat_score - a.threat_score;
    });

  const filters = [
    { id: "all", label: "All" },
    { id: "critical", label: "Critical" },
    { id: "high", label: "High" },
    { id: "acknowledged", label: "Acknowledged" },
  ];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div className="p-2.5 rounded-xl bg-severity-critical/[0.06] border border-severity-critical/10">
            <AlertTriangle className="w-5 h-5 text-severity-critical" strokeWidth={1.5} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-text-primary tracking-tight">Live Alerts</h2>
            <p className="text-[11px] text-text-muted mt-0.5 tracking-wide">
              {sorted.length} {sorted.length === 1 ? "alert" : "alerts"} in queue
            </p>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-2 border border-border-subtle">
          {filters.map((f) => (
            <button
              key={f.id}
              onClick={() => setSeverityFilter(f.id)}
              className={`px-3.5 py-1.5 rounded-lg text-[11px] font-medium tracking-wide transition-all duration-200 ${
                severityFilter === f.id
                  ? "bg-accent/10 text-accent"
                  : "text-text-muted hover:text-text-secondary hover:bg-white/[0.02]"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Alert list */}
      <div className="space-y-2">
        {sorted.map((alert) => (
          <AlertCard key={alert.alert_id} alert={alert} onClick={() => onSelectAlert(alert)} />
        ))}
        {sorted.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-text-muted">
            <div className="w-12 h-12 rounded-2xl bg-surface-2 border border-border-subtle flex items-center justify-center mb-4">
              <Filter className="w-5 h-5 opacity-30" strokeWidth={1.5} />
            </div>
            <p className="text-[13px] font-medium">No alerts match this filter</p>
            <p className="text-[11px] text-text-muted mt-1">Try selecting a different category</p>
          </div>
        )}
      </div>
    </div>
  );
}
