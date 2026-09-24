import { useState } from "react";
import type { Alert, AlertStatus } from "../types/api";
import {
  AlertTriangle, CheckCircle2, ChevronRight, Clock, Shield, AlertCircle,
  Info, XCircle, Ban, ShieldAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../services/api";
import { formatTime } from "../lib/time";
import { severityOf } from "../lib/severity";
import type { Severity } from "../lib/severity";

const SEVERITY: Record<Severity, {
  label: string; icon: LucideIcon; iconBox: string; iconText: string;
  badge: string; scoreText: string; card: string;
}> = {
  critical: {
    label: "CRITICAL", icon: AlertTriangle,
    iconBox: "bg-severity-critical-soft border-severity-critical/30",
    iconText: "text-severity-critical",
    badge: "bg-severity-critical-soft text-severity-critical border-severity-critical/30",
    scoreText: "text-severity-critical",
    card: "border-severity-critical/25 bg-gradient-to-br from-severity-critical/[0.04] to-transparent shadow-glow-critical",
  },
  high: {
    label: "HIGH", icon: AlertTriangle,
    iconBox: "bg-severity-high-soft border-severity-high/30",
    iconText: "text-severity-high",
    badge: "bg-severity-high-soft text-severity-high border-severity-high/30",
    scoreText: "text-severity-high",
    card: "border-severity-high/25 bg-gradient-to-br from-severity-high/[0.04] to-transparent shadow-glow-high",
  },
  medium: {
    label: "MEDIUM", icon: AlertCircle,
    iconBox: "bg-severity-medium-soft border-severity-medium/30",
    iconText: "text-severity-medium",
    badge: "bg-severity-medium-soft text-severity-medium border-severity-medium/30",
    scoreText: "text-severity-medium",
    card: "border-border-subtle bg-bg-card",
  },
  low: {
    label: "LOW", icon: Info,
    iconBox: "bg-severity-low-soft border-severity-low/30",
    iconText: "text-severity-low",
    badge: "bg-severity-low-soft text-severity-low border-severity-low/30",
    scoreText: "text-text-secondary",
    card: "border-border-subtle bg-bg-card",
  },
};

const STATUS_CHIP: Record<AlertStatus, { label: string; cls: string }> = {
  fired: { label: "ACTIVE", cls: "bg-severity-critical-soft text-severity-critical border-severity-critical/30" },
  enriched: { label: "ENRICHED", cls: "bg-enrichment-soft text-enrichment border-enrichment/30" },
  acknowledged: { label: "ACKNOWLEDGED", cls: "bg-status-ok-soft text-status-ok border-status-ok/30" },
  escalated: { label: "ESCALATED", cls: "bg-severity-high-soft text-severity-high border-severity-high/30" },
  false_positive: { label: "FALSE POSITIVE", cls: "bg-bg-elevated text-text-muted border-border-default" },
};

const TONE_EVENT: Record<string, string> = {
  crit: "bg-severity-critical-soft text-severity-critical border-severity-critical/30",
  ai: "bg-enrichment-soft text-enrichment border-enrichment/30",
  ok: "bg-status-ok-soft text-status-ok border-status-ok/30",
  idle: "bg-bg-elevated text-text-muted border-border-default",
};

export function IncomingAlert({
  alert,
  onAcknowledge,
  onFootprint,
}: {
  alert: Alert;
  onAcknowledge: () => void;
  onFootprint: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [snapshotOk, setSnapshotOk] = useState(true);

  const severity = severityOf(alert);
  const sev = SEVERITY[severity];
  const isOpen = alert.status === "fired" || alert.status === "enriched" || alert.status === "escalated";
  const canAcknowledge = alert.status !== "acknowledged" && alert.status !== "false_positive";
  const statusChip = STATUS_CHIP[alert.status];
  const hasSnapshot = Boolean(alert.snapshot_path) && snapshotOk;

  const timeline = [
    {
      time: alert.timestamp,
      event: "Detected",
      detail: alert.reason_detail || `${alert.reason.replace(/_/g, " ")} on ${alert.camera_id}`,
      tone: "crit",
    },
    ...(alert.footprint_entry_id !== null ? [{
      time: alert.created_at,
      event: "Logged",
      detail: `Hash-chained footprint entry #${alert.footprint_entry_id}`,
      tone: "idle",
    }] : []),
    ...(alert.enriched_at ? [{
      time: alert.enriched_at,
      event: "Enriched",
      detail: alert.ai_source ? `AI analysis via ${alert.ai_source}` : "AI analysis completed",
      tone: "ai",
    }] : []),
    ...(alert.status === "acknowledged" ? [{
      time: alert.enriched_at || alert.created_at,
      event: "Acknowledged",
      detail: "Acknowledged by operator",
      tone: "ok",
    }] : []),
  ];

  return (
    <div
      className={`group relative rounded-2xl p-5 border transition-all duration-300 ${
        isOpen ? sev.card : "border-border-subtle bg-bg-card"
      }`}
    >
      {isOpen && severity === "critical" && (
        <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-severity-critical animate-pulse-glow" aria-hidden="true" />
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center border flex-shrink-0 ${
            alert.status === "acknowledged" ? "bg-status-ok-soft border-status-ok/30" : sev.iconBox
          }`}>
            {alert.status === "false_positive" ? (
              <Ban className="w-5 h-5 text-text-muted" strokeWidth={1.8} />
            ) : alert.status === "escalated" ? (
              <ShieldAlert className={`w-5 h-5 ${sev.iconText}`} strokeWidth={1.8} />
            ) : (
              <sev.icon className={`w-5 h-5 ${alert.status === "acknowledged" ? "text-status-ok" : sev.iconText}`} strokeWidth={1.8} />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-[14px] font-semibold text-text-primary truncate">
                {alert.reason.replace(/_/g, " ")}
              </p>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider uppercase border ${statusChip.cls}`}>
                {statusChip.label}
              </span>
              {alert.status !== "acknowledged" && alert.status !== "false_positive" && (
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider uppercase border ${sev.badge}`}>
                  {sev.label}
                </span>
              )}
              {alert.plate_text && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-widest font-mono bg-bg-elevated text-accent border border-accent/30">
                  {alert.plate_text}
                </span>
              )}
            </div>
            <p className="text-[11px] text-text-muted mt-1 font-mono tracking-wide">
              {formatTime(alert.timestamp)} — {alert.camera_id}
            </p>
          </div>
        </div>

        {/* Threat Score */}
        <div className="flex-shrink-0 text-right">
          <div className={`text-2xl font-bold font-mono tabular-nums ${sev.scoreText}`} style={{ lineHeight: 1 }}>
            {(alert.threat_score * 100).toFixed(0)}
          </div>
          <div className="text-[9px] text-text-muted uppercase tracking-[0.2em] mt-0.5">THREAT</div>
        </div>
      </div>

      {/* Snapshot evidence (real capture; hidden if server 404s) */}
      {hasSnapshot && (
        <div className="mb-3 overflow-hidden rounded-xl border border-border-subtle">
          <img
            src={api.getSnapshotUrl(alert.alert_id)}
            alt={`Snapshot for alert on ${alert.camera_id}`}
            loading="lazy"
            onError={() => setSnapshotOk(false)}
            className="w-full h-28 object-cover"
          />
        </div>
      )}

      {/* Deterministic reason detail (rule-engine fact) */}
      {alert.reason_detail && (
        <p className="text-[12px] text-text-secondary leading-relaxed mb-2 font-mono">
          {alert.reason_detail}
        </p>
      )}

      {/* AI enrichment — appended below the deterministic reason, visually distinct */}
      {alert.ai_explanation && (
        <div className="mt-2 rounded-xl border-l-2 border-enrichment/60 bg-enrichment-soft px-3 py-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <Shield className="w-3 h-3 text-enrichment" strokeWidth={2} />
            <span className="text-[9px] font-bold tracking-[0.18em] uppercase text-enrichment">AI Enrichment</span>
            {alert.ai_source && (
              <span className="text-[9px] font-mono text-text-muted">· {alert.ai_source}</span>
            )}
          </div>
          <p className="text-[12px] text-text-secondary leading-relaxed">{alert.ai_explanation}</p>
        </div>
      )}

      {/* Expandable timeline */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full mt-3 flex items-center justify-between px-3 py-2 rounded-xl bg-bg-elevated/50 border border-border-hairline hover:bg-bg-elevated transition-colors duration-200"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          <Clock className="w-3.5 h-3.5" strokeWidth={1.8} />
          <span>Timeline ({timeline.length} events)</span>
        </div>
        <ChevronRight
          className={`w-4 h-4 text-text-muted transition-transform duration-200 ${expanded ? "rotate-90" : ""}`}
          strokeWidth={1.8}
        />
      </button>

      {expanded && (
        <div className="mt-4 animate-fade-in">
          <div className="relative">
            <div className="absolute left-5 top-0 bottom-0 w-px bg-border-subtle" />
            <div className="space-y-4 ml-5">
              {timeline.map((event, i) => (
                <div key={i} className="relative">
                  <div
                    className="absolute left-[-9px] top-1 w-2.5 h-2.5 rounded-full border-2"
                    style={{
                      borderColor: i === timeline.length - 1 ? "var(--color-status-ok)" : "var(--color-border-default)",
                      backgroundColor: i === timeline.length - 1 ? "var(--color-status-ok)" : "var(--color-bg-primary)",
                    }}
                  />
                  <div className="ml-4 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-semibold tracking-wider uppercase border ${TONE_EVENT[event.tone]}`}>
                        {event.event}
                      </span>
                      <span className="text-[10px] text-text-muted font-mono tracking-wide">
                        {formatTime(event.time)}
                      </span>
                    </div>
                    <p className="text-[12px] text-text-secondary ml-8">{event.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 mt-4 pt-4 border-t border-border-hairline">
        {canAcknowledge && (
          <button
            onClick={onAcknowledge}
            className="flex-1 min-h-[44px] py-3 rounded-xl bg-accent/10 border border-accent/25 text-accent text-[13px] font-medium hover:bg-accent/15 hover:border-accent/40 transition-all duration-200 flex items-center justify-center gap-2"
          >
            <CheckCircle2 className="w-4 h-4" strokeWidth={1.8} />
            Acknowledge
          </button>
        )}
        {alert.status === "acknowledged" && (
          <div className="flex-1 min-h-[44px] py-3 rounded-xl bg-status-ok/5 border border-status-ok/20 text-status-ok text-[13px] font-medium flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4" strokeWidth={1.8} />
            Acknowledged
          </div>
        )}
        {alert.status === "false_positive" && (
          <div className="flex-1 min-h-[44px] py-3 rounded-xl bg-bg-elevated border border-border-subtle text-text-muted text-[13px] font-medium flex items-center justify-center gap-2">
            <XCircle className="w-4 h-4" strokeWidth={1.8} />
            Closed as false positive
          </div>
        )}
        <button
          onClick={onFootprint}
          className="flex-1 min-h-[44px] py-3 rounded-xl bg-bg-elevated border border-border-subtle text-text-secondary text-[13px] font-medium hover:text-text-primary hover:border-border-strong flex items-center justify-center gap-2 transition-all duration-200"
        >
          Footprint
          <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
