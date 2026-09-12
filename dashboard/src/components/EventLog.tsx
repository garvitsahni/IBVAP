import { useState, useEffect } from "react";
import { api } from "../services/api";
import type { Alert } from "../types/api";
import { Search, Activity } from "lucide-react";

const statusStyles: Record<string, string> = {
  acknowledged: "bg-status-ok/[0.06] text-status-ok border-status-ok/10",
  enriched: "bg-enrichment/[0.06] text-enrichment border-enrichment/10",
  fired: "bg-severity-high/[0.06] text-severity-high border-severity-high/10",
};

export function EventLog() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.getAlerts("limit=200").then(setAlerts).catch(() => {});
  }, []);

  const filtered = alerts.filter((a) => {
    if (!filter) return true;
    const f = filter.toLowerCase();
    return a.reason.includes(f) || a.camera_id.includes(f) || a.object_id.includes(f);
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="p-2.5 rounded-xl bg-accent/[0.06] border border-accent/10">
          <Activity className="w-5 h-5 text-accent" strokeWidth={1.5} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-text-primary tracking-tight">Event Log</h2>
          <p className="text-[11px] text-text-muted mt-0.5 tracking-wide">
            {filtered.length} events
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={1.5} />
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search events..."
          className="w-full bg-surface-2 border border-border-subtle rounded-xl pl-10 pr-4 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/30 transition-all duration-200"
        />
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-border-subtle overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left bg-surface-2/50">
              <th className="px-5 py-3.5 text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">Time</th>
              <th className="px-5 py-3.5 text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">Camera</th>
              <th className="px-5 py-3.5 text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">Reason</th>
              <th className="px-5 py-3.5 text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">Score</th>
              <th className="px-5 py-3.5 text-[10px] font-semibold text-text-muted uppercase tracking-[0.15em]">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a, i) => (
              <tr
                key={a.alert_id}
                className={`border-t border-border-subtle hover:bg-white/[0.015] transition-colors duration-150 ${
                  i % 2 === 0 ? "bg-surface-1" : "bg-black"
                }`}
              >
                <td className="px-5 py-3.5 font-mono text-[11px] text-text-muted tabular-nums">
                  {new Date(a.timestamp).toLocaleTimeString()}
                </td>
                <td className="px-5 py-3.5 font-mono text-[11px] text-text-secondary tracking-wide">{a.camera_id}</td>
                <td className="px-5 py-3.5 text-text-primary text-[13px]">{a.reason}</td>
                <td className="px-5 py-3.5 font-mono text-[11px] tabular-nums">
                  <span className={
                    a.threat_score >= 0.8
                      ? "text-severity-critical"
                      : a.threat_score >= 0.5
                      ? "text-severity-high"
                      : "text-text-muted"
                  }>
                    {a.threat_score.toFixed(2)}
                  </span>
                </td>
                <td className="px-5 py-3.5">
                  <span className={`text-[9px] font-semibold uppercase tracking-[0.15em] px-2 py-1 rounded-md border ${statusStyles[a.status] || "bg-surface-3 text-text-muted border-border-default"}`}>
                    {a.status}
                  </span>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-16 text-center text-text-muted text-[13px]">
                  No events found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
