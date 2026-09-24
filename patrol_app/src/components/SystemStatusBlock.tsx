import { useState, useEffect } from "react";
import {
  ChevronUp, ChevronDown, ShieldCheck, ShieldAlert, AlertTriangle,
  Wifi, WifiOff, EyeOff, Eye, Snowflake, Activity, Circle, Cpu, Radar,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../services/api";
import type { Camera, CameraHealthEntry, SystemHealth } from "../types/api";
import { secondsSince, formatRelative } from "../lib/time";

type Tone = "ok" | "warn" | "bad" | "idle";

const TONE: Record<Tone, { box: string; text: string; chip: string }> = {
  ok: {
    box: "bg-status-ok/10 border-status-ok/25",
    text: "text-status-ok",
    chip: "bg-status-ok/10 text-status-ok border-status-ok/25",
  },
  warn: {
    box: "bg-severity-high/10 border-severity-high/25",
    text: "text-severity-high",
    chip: "bg-severity-high/10 text-severity-high border-severity-high/25",
  },
  bad: {
    box: "bg-severity-critical/10 border-severity-critical/25",
    text: "text-severity-critical",
    chip: "bg-severity-critical/10 text-severity-critical border-severity-critical/25",
  },
  idle: {
    box: "bg-bg-elevated border-border-default",
    text: "text-text-muted",
    chip: "bg-bg-elevated text-text-muted border-border-subtle",
  },
};

function cameraStatusUi(status: string): { label: string; tone: Tone; icon: LucideIcon } {
  switch (status) {
    case "ok": return { label: "OK", tone: "ok", icon: Wifi };
    case "blinding": return { label: "BLINDING", tone: "bad", icon: EyeOff };
    case "obscured": return { label: "OBSCURED", tone: "bad", icon: Eye };
    case "frozen": return { label: "FROZEN", tone: "bad", icon: Snowflake };
    case "tamper": return { label: "TAMPER", tone: "bad", icon: ShieldAlert };
    case "drift": return { label: "DRIFT", tone: "warn", icon: Activity };
    case "offline": return { label: "OFFLINE", tone: "bad", icon: WifiOff };
    case "degraded": return { label: "DEGRADED", tone: "warn", icon: Activity };
    case "unknown": return { label: "NO REPORT", tone: "idle", icon: WifiOff };
    default: return { label: status.toUpperCase() || "?", tone: "idle", icon: Circle };
  }
}

const STALE_AFTER_S = 90;

interface CameraRow {
  camera_id: string;
  health: CameraHealthEntry | undefined;
  registered: boolean;
}

export function SystemStatusBlock() {
  const [system, setSystem] = useState<SystemHealth | null>(null);
  const [rows, setRows] = useState<CameraRow[]>([]);
  const [fetchFailed, setFetchFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [sys, health, cams] = await Promise.all([
          api.getSystemHealth(),
          api.getCameraHealth(),
          api.getCameras(),
        ]);
        if (!alive) return;
        const ids = new Set<string>([
          ...Object.keys(health),
          ...cams.map((c: Camera) => c.camera_id),
        ]);
        setRows(
          [...ids].sort().map((camera_id) => ({
            camera_id,
            health: health[camera_id],
            registered: cams.some((c: Camera) => c.camera_id === camera_id),
          }))
        );
        setSystem(sys);
        setFetchFailed(false);
      } catch {
        if (alive) setFetchFailed(true);
      } finally {
        if (alive) setLoaded(true);
      }
    };
    load();
    const interval = setInterval(load, 12000);
    return () => { alive = false; clearInterval(interval); };
  }, []);

  const overall = fetchFailed
    ? { label: "UNAVAILABLE", tone: "idle" as Tone, icon: Circle }
    : system?.status === "ok"
    ? { label: "SYSTEM OK", tone: "ok" as Tone, icon: ShieldCheck }
    : system?.status === "degraded"
    ? { label: "DEGRADED", tone: "warn" as Tone, icon: AlertTriangle }
    : system?.status === "critical"
    ? { label: "COMPROMISED", tone: "bad" as Tone, icon: ShieldAlert }
    : { label: "UNKNOWN", tone: "idle" as Tone, icon: Circle };

  const okCount = rows.filter((r) => cameraStatusUi(r.health?.status ?? (r.registered ? "unknown" : "offline")).tone === "ok").length;

  return (
    <div className="card rounded-2xl p-5 animate-slide-up stagger-1">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center">
            <Cpu className="w-5 h-5 text-accent" strokeWidth={1.8} />
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-text-primary tracking-tight">System Status</h3>
            <p className="text-[10px] text-text-muted tracking-[0.15em] uppercase">Field telemetry</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-wider uppercase border ${TONE[overall.tone].chip}`}>
            <overall.icon className="w-3 h-3" strokeWidth={2} />
            {overall.label}
          </span>
          {!loaded && !fetchFailed && (
            <span className="text-[10px] text-text-muted uppercase tracking-widest">loading…</span>
          )}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="p-2 rounded-xl bg-bg-elevated border border-border-subtle text-text-muted hover:text-text-secondary hover:border-border-strong transition-all duration-200"
            aria-label={showDetails ? "Hide details" : "Show details"}
            aria-expanded={showDetails}
          >
            {showDetails ? <ChevronUp className="w-4 h-4" strokeWidth={1.8} /> : <ChevronDown className="w-4 h-4" strokeWidth={1.8} />}
          </button>
        </div>
      </div>

      {/* Loud non-normal operating chips (real values from /system/health) */}
      {system && (system.detection_tier !== "normal" || system.power_mode !== "normal" || system.coverage_gaps.length > 0) && (
        <div className="flex items-center gap-2 flex-wrap mb-4">
          {system.detection_tier !== "normal" && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase border bg-severity-high/10 text-severity-high border-severity-high/30">
              <Radar className="w-3 h-3" strokeWidth={2} />
              Detection tier: {system.detection_tier}
            </span>
          )}
          {system.power_mode !== "normal" && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase border bg-severity-high/10 text-severity-high border-severity-high/30">
              Power: {system.power_mode}
            </span>
          )}
          {system.coverage_gaps.length > 0 && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase border bg-severity-critical/10 text-severity-critical border-severity-critical/30">
              {system.coverage_gaps.length} coverage gap{system.coverage_gaps.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {/* Cameras */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted">Cameras</span>
          <span className="text-[11px] text-text-muted font-mono tabular-nums">
            {okCount}/{rows.length} healthy
          </span>
        </div>

        {!loaded && rows.length === 0 && (
          <div className="h-10 rounded-xl bg-bg-elevated/50 border border-border-hairline animate-shimmer" />
        )}
        {loaded && rows.length === 0 && (
          <p className="text-[12px] text-text-muted px-1 py-2">
            {fetchFailed ? "Camera health unavailable — server unreachable." : "No cameras registered."}
          </p>
        )}

        <div className="flex flex-col gap-2">
          {rows.map((row) => {
            const rawStatus = row.health?.status ?? (row.registered ? "unknown" : "offline");
            const ui = cameraStatusUi(rawStatus);
            const ageS = secondsSince(row.health?.last_seen ?? row.health?.last_updated);
            const stale = ageS !== null && ageS > STALE_AFTER_S;
            const tone: Tone = stale && ui.tone === "ok" ? "bad" : ui.tone;
            const Icon = ui.icon;

            return (
              <div
                key={row.camera_id}
                className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl bg-bg-elevated/50 border border-border-hairline"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className={`w-8 h-8 rounded-lg border flex items-center justify-center flex-shrink-0 ${TONE[tone].box}`}>
                    <Icon className={`w-4 h-4 ${TONE[tone].text}`} strokeWidth={1.8} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[12px] font-medium text-text-primary truncate">{row.camera_id}</p>
                    <p className="text-[10px] text-text-muted mt-0.5">
                      {stale ? `stale — seen ${formatRelative(row.health?.last_seen ?? row.health?.last_updated)}` : ui.label}
                      {stale && ui.tone !== "ok" ? ` (${ui.label})` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {row.health?.reduced_accuracy_mode && (
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider uppercase bg-severity-high/15 text-severity-high border border-severity-high/40">
                      Reduced acc.
                    </span>
                  )}
                  {row.health?.detect_p95_ms !== undefined && (
                    <span className={`text-[10px] font-mono tabular-nums ${row.health.detect_p95_ms > 100 ? "text-severity-high" : "text-text-muted"}`}>
                      {Math.round(row.health.detect_p95_ms)}ms
                    </span>
                  )}
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider uppercase border ${TONE[tone].chip}`}>
                    {stale ? "stale" : ui.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Details: detection tier / power mode / coverage gaps (real system health fields) */}
      {showDetails && system && (
        <div className="border-t border-border-hairline pt-4 mt-4 animate-slide-down">
          <div className="flex flex-col gap-2">
            {[
              { label: "Detection tier", value: system.detection_tier, warn: system.detection_tier !== "normal" },
              { label: "Power mode", value: system.power_mode, warn: system.power_mode !== "normal" },
              { label: "Coverage gaps", value: String(system.coverage_gaps.length), warn: system.coverage_gaps.length > 0 },
              { label: "Overall status", value: system.status, warn: system.status !== "ok" },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between px-3 py-2 rounded-xl bg-bg-elevated/50 border border-border-hairline">
                <span className="text-[11px] text-text-muted">{item.label}</span>
                <span className={`text-[11px] font-mono ${item.warn ? "text-severity-high font-semibold" : "text-text-secondary"}`}>
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
