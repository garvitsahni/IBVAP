import { useEffect, useState, useCallback } from "react";
import { Shield, Bell, BellOff, Radio, Package } from "lucide-react";
import { IncomingAlert } from "./components/IncomingAlert";
import { FootprintSummary } from "./components/FootprintSummary";
import { DeviceSelector } from "./components/DeviceSelector";
import { api } from "./services/api";
import { useSSE } from "./hooks/useSSE";
import type { Alert } from "./types/api";

export default function App() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [deviceId, setDeviceId] = useState(() => api.getDeviceId());
  const [notifEnabled, setNotifEnabled] = useState(() => {
    return typeof Notification !== "undefined" && Notification.permission === "granted";
  });
  const { on } = useSSE("/api/v1/alerts/stream");

  const handleNewAlert = useCallback(
    (data: Record<string, unknown>) => {
      const alert = data as unknown as Alert;
      setAlerts((prev) => [alert, ...prev]);
      if (notifEnabled && typeof Notification !== "undefined") {
        new Notification("IBVAP Alert", {
          body: `${alert.reason} — Score ${alert.threat_score.toFixed(2)}`,
          icon: "/shield.svg",
        });
      }
    },
    [notifEnabled]
  );

  useEffect(() => {
    on("alert_fired", handleNewAlert);
    on("alert_enriched", (data) => {
      const updated = data as unknown as Alert;
      setAlerts((prev) =>
        prev.map((a) => (a.alert_id === updated.alert_id ? updated : a))
      );
    });
  }, [on, handleNewAlert]);

  useEffect(() => {
    api.getAlerts("limit=10").then(setAlerts).catch(() => {});
  }, []);

  const toggleNotifications = async () => {
    if (!notifEnabled && typeof Notification !== "undefined") {
      const perm = await Notification.requestPermission();
      setNotifEnabled(perm === "granted");
    } else {
      setNotifEnabled(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex flex-col">
      {/* Header */}
      <header className="border-b border-border-subtle bg-black/80 backdrop-blur-2xl sticky top-0 z-50">
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
              className="p-2 rounded-xl bg-surface-2 border border-border-subtle text-text-muted hover:text-text-primary transition-all duration-200"
              title={notifEnabled ? "Disable notifications" : "Enable notifications"}
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
      <main className="flex-1 max-w-2xl mx-auto w-full px-5 py-8">
        {/* Live indicator */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-2 border border-border-subtle">
              <Radio className="w-3 h-3 text-status-ok animate-[pulse-glow_2s_ease-in-out_infinite]" strokeWidth={2} />
              <span className="text-[11px] font-medium text-text-secondary tracking-wide">Live</span>
            </div>
          </div>
          <span className="text-[11px] text-text-muted font-mono tabular-nums">
            {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Content */}
        <div className="space-y-6">
          {selectedAlert ? (
            <div className="space-y-6 animate-fade-in">
              <FootprintSummary
                footprint={{
                  object_id: selectedAlert.object_id,
                  entries: [],
                  is_valid: true,
                  first_seen: selectedAlert.timestamp,
                  last_seen: selectedAlert.timestamp,
                  camera_hops: 1,
                }}
                onBack={() => setSelectedAlert(null)}
              />
              <button
                onClick={() => setSelectedAlert(null)}
                className="w-full py-3 rounded-xl bg-surface-2 border border-border-subtle text-[13px] font-medium text-text-muted hover:text-text-primary hover:border-border-strong transition-all duration-200"
              >
                Back to alerts
              </button>
            </div>
          ) : alerts.length > 0 ? (
            <div className="space-y-3">
              {alerts.map((a: Alert) => (
                <div key={a.alert_id} className="animate-fade-in">
                  <IncomingAlert
                    alert={a}
                    onAcknowledge={async () => {
                      await api.acknowledgeAlert(a.alert_id);
                      setAlerts((prev) =>
                        prev.map((x) =>
                          x.alert_id === a.alert_id
                            ? { ...x, status: "acknowledged" as const }
                            : x
                        )
                      );
                    }}
                    onFootprint={() => setSelectedAlert(a)}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-32 animate-fade-in">
              <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-border-subtle flex items-center justify-center mb-5">
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
