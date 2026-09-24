import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertFeed } from '@/components/alert/AlertFeed';
import { AlertDetailPanel } from '@/components/alert/AlertDetailPanel';
import { api } from '@/services/api';
import { useSSE } from '@/hooks/useSSE';
import type { Alert as ApiAlert } from '@/types/api';
import { mapApiAlert, type FeedAlert } from '@/lib/alerts';

export function AlertsPage() {
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getAlerts()
      .then((raw) => setAlerts(raw.map(mapApiAlert)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const { on } = useSSE('/api/v1/alerts/stream');
  useEffect(() => {
    on('alert_fired', (data) => {
      const raw = data as unknown as ApiAlert;
      setAlerts((prev) => [mapApiAlert(raw), ...prev]);
    });
  }, [on]);

  const handleAcknowledge = async (id: string) => {
    try {
      await api.acknowledgeAlert(id);
      setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, status: 'acknowledged' } : a));
    } catch {}
  };

  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Alerts</h1>
        <p className="text-sm text-text-secondary">
          Threat and anomaly alerts generated from detections.
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="animate-pulse space-y-2 rounded-md border border-border bg-surface p-4">
              <div className="h-3 w-3/4 rounded bg-surface-2" />
              <div className="h-2.5 w-1/3 rounded bg-surface-2" />
            </div>
          ))}
        </div>
      ) : (
        <AlertFeed
          alerts={alerts}
          selectedId={selectedAlertId ?? undefined}
          onSelect={(a) => setSelectedAlertId(a.id)}
        />
      )}

      <AlertDetailPanel
        alert={selectedAlert}
        onClose={() => setSelectedAlertId(null)}
        onAcknowledge={handleAcknowledge}
      />
    </motion.div>
  );
}
