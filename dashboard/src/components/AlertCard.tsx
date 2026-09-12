import type { Alert } from "../types/api";
import { AlertTriangle, Clock, CheckCircle2 } from "lucide-react";

const severity = (score: number) => {
  if (score >= 0.8)
    return {
      label: "CRITICAL",
      color: "text-severity-critical",
      bg: "bg-severity-critical/[0.04]",
      border: "border-severity-critical/20",
      ring: "shadow-[0_0_30px_-8px] shadow-severity-critical/30",
      dot: "bg-severity-critical",
    };
  if (score >= 0.5)
    return {
      label: "HIGH",
      color: "text-severity-high",
      bg: "bg-severity-high/[0.03]",
      border: "border-severity-high/15",
      ring: "shadow-[0_0_24px_-8px] shadow-severity-high/20",
      dot: "bg-severity-high",
    };
  if (score >= 0.3)
    return {
      label: "MEDIUM",
      color: "text-severity-medium",
      bg: "bg-severity-medium/[0.03]",
      border: "border-severity-medium/10",
      ring: "",
      dot: "bg-severity-medium",
    };
  return {
    label: "LOW",
    color: "text-text-muted",
    bg: "bg-white/[0.01]",
    border: "border-border-default",
    ring: "",
    dot: "bg-text-muted",
  };
};

export function AlertCard({ alert, onClick }: { alert: Alert; onClick?: () => void }) {
  const s = severity(alert.threat_score);
  const acknowledged = alert.status === "acknowledged";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-5 rounded-2xl border ${s.border} ${s.bg} ${s.ring} backdrop-blur-sm hover:bg-white/[0.03] transition-all duration-300 group animate-fade-in`}
    >
      <div className="flex items-start justify-between gap-6">
        <div className="flex items-start gap-4 min-w-0">
          {/* Status indicator */}
          <div className="mt-0.5 relative">
            <div className={`w-9 h-9 rounded-xl ${s.bg} border ${s.border} flex items-center justify-center`}>
              {acknowledged ? (
                <CheckCircle2 className="w-4 h-4 text-status-ok" strokeWidth={1.5} />
              ) : (
                <AlertTriangle className={`w-4 h-4 ${s.color}`} strokeWidth={1.5} />
              )}
            </div>
            {!acknowledged && (
              <div className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${s.dot} animate-[pulse-glow_2s_ease-in-out_infinite]`} />
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2.5 mb-1.5">
              <span className="font-mono text-[11px] text-text-muted tracking-wider">{alert.camera_id}</span>
              <span className={`text-[9px] font-bold tracking-[0.15em] ${s.color}`}>{s.label}</span>
            </div>
            <p className="text-[13px] font-medium text-text-primary truncate leading-relaxed">{alert.reason}</p>
            <div className="flex items-center gap-4 mt-2.5 text-[11px] text-text-muted">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3 h-3" strokeWidth={1.5} />
                {new Date(alert.timestamp).toLocaleTimeString()}
              </span>
              <span className="font-mono tracking-wide">
                {alert.threat_score.toFixed(2)}
              </span>
              {acknowledged && (
                <span className="text-status-ok flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" strokeWidth={1.5} />
                  Ack
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Score */}
        <div className="shrink-0 text-right">
          <div className={`text-xl font-bold font-mono tabular-nums ${s.color}`}>
            {(alert.threat_score * 100).toFixed(0)}
          </div>
          <div className="text-[9px] text-text-muted uppercase tracking-[0.2em] mt-0.5">Score</div>
        </div>
      </div>
    </button>
  );
}
