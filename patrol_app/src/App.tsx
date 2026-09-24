import { useEffect, useState, useCallback, useMemo } from "react";
import { Shield, Bell, BellOff, Package, ChevronLeft, Radio, AlertTriangle } from "lucide-react";
import { IncomingAlert } from "./components/IncomingAlert";
import { severityOf } from "./lib/severity";
import { FootprintSummary } from "./components/FootprintSummary";
import { SystemStatusBlock } from "./components/SystemStatusBlock";
import { DeviceSelector } from "./components/DeviceSelector";
import { api } from "./services/api";
import { useSSE } from "./hooks/useSSE";
import { useNotifications } from "./hooks/useNotifications";
import type { Alert, AlertStatus, DashboardStats, ThreatLevel } from "./types/api";

const SEVERITY_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function statusRank(status: AlertStatus): number {
  switch (status) {
    case "fired":
    case "escalated":
      return 0;
    case "enriched":
      return 1;
    case "acknowledged":
      return 2;
    case "false_positive":
      return 3;
    default:
      return 1;
  }
}

// SSE alert_fired is a PARTIAL payload — normalize to a full Alert so no
// field is ever undefined downstream (created_at falls back to timestamp).
function normalizeFired(data: Record<string, unknown>): Alert {
  const d = data as Partial<Alert> & { threat_level?: ThreatLevel };
  const timestamp = String(d.timestamp ?? new Date().toISOString());
  return {
    id: -1,
    alert_id: String(d.alert_id ?? ""),
    object_id: String(d.object_id ?? ""),
    camera_id: String(d.camera_id ?? ""),
    timestamp,
    reason: String(d.reason ?? "alert"),
    status: d.status ?? "fired",
    threat_score: Number(d.threat_score ?? 0),
    threat_level: d.threat_level ?? null,
    clip_path: null,
    ai_explanation: null,
    ai_source: null,
    trajectory_projection: null,
    plate_text: d.plate_text ?? null,
    reason_detail: d.reason_detail ?? null,
    snapshot_path: d.snapshot_path ?? null,
    footprint_entry_id: null,
    created_at: timestamp,
    enriched_at: null,
  };
}

export default function App() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deviceId, setDeviceId] = useState(() => api.getDeviceId());
  const [notifEnabled, setNotifEnabled] = useState(true);
  const { connected, on } = useSSE("/api/v1/alerts/stream");
  const { notify, requestPermission } = useNotifications();

  const selected = useMemo(
    () => (selectedId ? alerts.find((a) => a.alert_id === selectedId) ?? null : null),
    [selectedId, alerts]
  );

  const sorted = useMemo(() => {
    return [...alerts].sort((a, b) => {
      const ra = statusRank(a.status);
      const rb = statusRank(b.status);
      if (ra !== rb) return ra - rb;
      const sa = SEVERITY_RANK[severityOf(a)] ?? 9;
      const sb = SEVERITY_RANK[severityOf(b)] ?? 9;
      if (sa !== sb) return sa - sb;
      if (b.threat_score !== a.threat_score) return b.threat_score - a.threat_score;
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });
  }, [alerts]);

  const fetchPage = useCallback(
    () =>
      Promise.all([
        api.getAlerts("limit=20"),
        api.getStats().catch(() => null),
      ]),
    []
  );

  useEffect(() => {
    let alive = true;
    fetchPage()
      .then(([list, s]) => {
        if (!alive) return;
        setAlerts(list);
        setStats(s);
        setLoadFailed(false);
        setLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        setLoadFailed(true);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [fetchPage]);

  const retry = () => {
    setLoading(true);
    setLoadFailed(false);
    fetchPage()
      .then(([list, s]) => {
        setAlerts(list);
        setStats(s);
        setLoadFailed(false);
        setLoading(false);
      })
      .catch(() => {
        setLoadFailed(true);
        setLoading(false);
      });
  };

  const handleNewAlert = useCallback(
    (data: Record<string, unknown>) => {
      const incoming = normalizeFired(data);
      if (!incoming.alert_id) return;
      setAlerts((prev) =>
        prev.some((a) => a.alert_id === incoming.alert_id)
          ? prev.map((a) => (a.alert_id === incoming.alert_id ? { ...a, ...incoming } : a))
          : [incoming, ...prev]
      );
      if (notifEnabled) {
        const level = incoming.threat_level
          ? incoming.threat_level.toUpperCase()
          : severityOf(incoming).toUpperCase();
        notify(
          "IBVAP Alert",
          `${level} · ${incoming.reason.replace(/_/g, " ")} · ${incoming.camera_id}`
        );
      }
    },
    [notifEnabled, notify]
  );

  const handleEnriched = useCallback((data: Record<string, unknown>) => {
    const alertId = String(data.alert_id ?? "");
    if (!alertId) return;
    // alert_enriched is also a PARTIAL payload — MERGE, never replace, then
    // refetch the authoritative record so snapshot/footprint ids arrive too.
    const aiExplanation = (data.ai_explanation as string | null) ?? null;
    const projection = (data.trajectory_projection as Record<string, unknown> | null) ?? null;
    setAlerts((prev) =>
      prev.map((a) =>
        a.alert_id === alertId
          ? {
              ...a,
              ai_explanation: aiExplanation ?? a.ai_explanation,
              trajectory_projection: projection ?? a.trajectory_projection,
              status: a.status === "fired" ? "enriched" : a.status,
            }
          : a
      )
    );
    api
      .getAlert(alertId)
      .then((fresh) => {
        setAlerts((prev) => prev.map((a) => (a.alert_id === alertId ? fresh : a)));
      })
      .catch(() => {
        // partial merge above already shows the explanation; full record lands on next poll
      });
  }, []);

  useEffect(() => {
    on("alert_fired", handleNewAlert);
    on("alert_enriched", handleEnriched);
  }, [on, handleNewAlert, handleEnriched]);

  const toggleNotifications = useCallback(async () => {
    if (!notifEnabled) {
      await requestPermission();
      setNotifEnabled(true);
      // unlock audio context with this user gesture
      notify("Notifications on", "You will be alerted on new events");
    } else {
      setNotifEnabled(false);
    }
  }, [notifEnabled, notify, requestPermission]);

  const acknowledge = useCallback(async (alert: Alert) => {
    try {
      await api.acknowledgeAlert(alert.alert_id);
      setAlerts((prev) =>
        prev.map((x) =>
          x.alert_id === alert.alert_id ? { ...x, status: "acknowledged" as const } : x
        )
      );
    } catch (e) {
      console.warn("Acknowledge failed:", e);
    }
  }, []);

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col">
      {/* Header */}
      <header className="border-b border-border-subtle bg-bg-glass backdrop-blur-2xl sticky top-0 z-50 safe-top">
        <div className="max-w-2xl mx-auto px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center border border-accent/10">
              <Shield className="w-5 h-5 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <h1 className="text-[15px] font-semibold text-text-primary tracking-tight">IBVAP Patrol</h1>
              <p className="text-[10px] text-text-muted tracking-[0.2em] uppercase">Mobile Unit</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <DeviceSelector deviceId={deviceId} onChange={setDeviceId} />
            <button
              onClick={toggleNotifications}
              className={`p-2 rounded-xl border transition-all duration-200 ${
                notifEnabled
                  ? "bg-accent/10 border-accent/30 text-accent"
                  : "bg-bg-card border-border-subtle text-text-muted hover:text-text-primary"
              }`}
              title={notifEnabled ? "Disable alerts" : "Enable alerts"}
              aria-pressed={notifEnabled}
            >
              {notifEnabled ? (
                <Bell className="w-4 h-4" strokeWidth={1.5} />
              ) : (
                <BellOff className="w-4 h-4" strokeWidth={1.5} />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-2xl mx-auto w-full px-5 py-6 safe-bottom">
        {/* Status row: real SSE connection state + stats */}
        <div className="flex items-center justify-between gap-2 flex-wrap mb-5">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
              connected
                ? "bg-status-ok/10 border-status-ok/25"
                : "bg-severity-high/10 border-severity-high/25"
            }`}
            title={connected ? "Connected to alert stream" : "Reconnecting to alert stream…"}
          >
            <Radio
              className={`w-3 h-3 ${connected ? "text-status-ok animate-pulse-glow" : "text-severity-high"}`}
              strokeWidth={2}
            />
            <span className={`text-[11px] font-medium tracking-wide ${connected ? "text-status-ok" : "text-severity-high"}`}>
              {connected ? "Live" : "Reconnecting…"}
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {stats && (
              <>
                <span className="px-2.5 py-1 rounded-full bg-bg-card border border-border-subtle text-[10px] font-mono text-text-secondary">
                  TODAY <span className="text-text-primary font-semibold">{stats.total_alerts_today}</span>
                </span>
                {stats.alerts_by_severity.critical > 0 && (
                  <span className="px-2.5 py-1 rounded-full bg-severity-critical-soft border border-severity-critical/30 text-[10px] font-mono text-severity-critical font-semibold">
                    CRIT {stats.alerts_by_severity.critical}
                  </span>
                )}
                {stats.alerts_by_severity.high > 0 && (
                  <span className="px-2.5 py-1 rounded-full bg-severity-high-soft border border-severity-high/30 text-[10px] font-mono text-severity-high font-semibold">
                    HIGH {stats.alerts_by_severity.high}
                  </span>
                )}
                <span className="px-2.5 py-1 rounded-full bg-bg-card border border-border-subtle text-[10px] font-mono text-text-secondary">
                  WATCHLIST <span className="text-text-primary font-semibold">{stats.active_watchlist_entries}</span>
                </span>
              </>
            )}
            <span className="px-2.5 py-1 rounded-full bg-bg-card border border-border-subtle text-[10px] font-mono text-text-muted">
              {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {/* System status (real telemetry) */}
        {!selected && <SystemStatusBlock />}

        {/* Content */}
        <div className="space-y-4 mt-5">
          {selected ? (
            <div className="space-y-4 animate-fade-in">
              <button
                onClick={() => setSelectedId(null)}
                className="flex items-center gap-1.5 text-[13px] font-medium text-text-muted hover:text-text-primary transition-colors"
              >
                <ChevronLeft className="w-4 h-4" strokeWidth={1.8} />
                Back to alerts
              </button>
              <IncomingAlert
                alert={selected}
                onAcknowledge={() => acknowledge(selected)}
                onFootprint={() => {}}
              />
              <FootprintSummary objectId={selected.object_id} />
            </div>
          ) : loading ? (
            <div className="space-y-4">
              {[0, 1].map((i) => (
                <div key={i} className="card rounded-2xl p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-11 h-11 rounded-xl bg-bg-elevated animate-shimmer" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3.5 w-2/5 rounded bg-bg-elevated animate-shimmer" />
                      <div className="h-2.5 w-1/4 rounded bg-bg-elevated animate-shimmer" />
                    </div>
                    <div className="h-7 w-9 rounded bg-bg-elevated animate-shimmer" />
                  </div>
                  <div className="h-9 rounded-xl bg-bg-elevated/50 animate-shimmer" />
                </div>
              ))}
            </div>
          ) : loadFailed ? (
            <div className="card rounded-2xl p-6 animate-fade-in text-center">
              <AlertTriangle className="w-8 h-8 text-severity-high mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-[13px] font-medium text-text-secondary">Can&apos;t reach the fusion server</p>
              <p className="text-[11px] text-text-muted mt-1.5">Alerts will appear once the connection is restored.</p>
              <button
                onClick={retry}
                className="mt-4 px-4 py-2 rounded-xl bg-bg-elevated border border-border-subtle text-[12px] text-text-secondary hover:text-text-primary hover:border-border-strong transition-all"
              >
                Retry
              </button>
            </div>
          ) : sorted.length > 0 ? (
            <div className="space-y-3">
              {sorted.map((a) => (
                <div key={a.alert_id} className="animate-fade-in">
                  <IncomingAlert
                    alert={a}
                    onAcknowledge={() => acknowledge(a)}
                    onFootprint={() => setSelectedId(a.alert_id)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-28 animate-fade-in">
              <div className="w-14 h-14 rounded-2xl bg-bg-card border border-border-subtle flex items-center justify-center mb-5">
                <Package className="w-6 h-6 text-text-muted opacity-30" strokeWidth={1.5} />
              </div>
              <p className="text-[13px] font-medium text-text-secondary">Standing by</p>
              <p className="text-[11px] text-text-muted mt-1.5">Waiting for incoming alerts</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
