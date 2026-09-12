import type { Alert } from "../types/api";
import { AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";

export function IncomingAlert({
  alert,
  onAcknowledge,
  onFootprint,
}: {
  alert: Alert;
  onAcknowledge: () => void;
  onFootprint: () => void;
}) {
  const isAcknowledged = alert.status === "acknowledged";
  const isHigh = alert.threat_score >= 0.5;

  return (
    <div
      className={`rounded-2xl border p-6 ${
        isHigh && !isAcknowledged
          ? "border-severity-critical/20 bg-gradient-to-br from-severity-critical/[0.04] to-transparent shadow-[0_0_40px_-12px] shadow-severity-critical/20"
          : "border-border-subtle bg-surface-1"
      }`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              isAcknowledged
                ? "bg-status-ok/[0.06] border border-status-ok/10"
                : "bg-severity-critical/[0.06] border border-severity-critical/10"
            }`}>
              {isAcknowledged ? (
                <CheckCircle2 className="w-5 h-5 text-status-ok" strokeWidth={1.5} />
              ) : (
                <AlertTriangle className="w-5 h-5 text-severity-critical" strokeWidth={1.5} />
              )}
            </div>
            {!isAcknowledged && (
              <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-severity-critical animate-[pulse-glow_2s_ease-in-out_infinite]" />
            )}
          </div>
          <div>
            <p className="text-[13px] font-medium text-text-primary">{alert.reason}</p>
            <p className="text-[11px] text-text-muted mt-0.5 font-mono tracking-wide">
              {new Date(alert.timestamp).toLocaleTimeString()} — {alert.camera_id}
            </p>
          </div>
        </div>

        {/* Threat score */}
        <div className="text-right">
          <div className={`text-2xl font-bold font-mono tabular-nums ${
            alert.threat_score >= 0.8
              ? "text-severity-critical"
              : alert.threat_score >= 0.5
              ? "text-severity-high"
              : "text-text-secondary"
          }`}>
            {(alert.threat_score * 100).toFixed(0)}
          </div>
          <div className="text-[9px] text-text-muted uppercase tracking-[0.2em]">Score</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        {!isAcknowledged && (
          <button
            onClick={onAcknowledge}
            className="flex-1 py-2.5 rounded-xl bg-accent/10 border border-accent/20 text-accent text-[13px] font-medium hover:bg-accent/15 transition-all duration-200"
          >
            Acknowledge
          </button>
        )}
        {alert.footprint_entry_id && (
          <button
            onClick={onFootprint}
            className="flex-1 py-2.5 rounded-xl bg-surface-2 border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-text-primary hover:border-border-strong flex items-center justify-center gap-2 transition-all duration-200"
          >
            Footprint
            <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        )}
      </div>
    </div>
  );
}
