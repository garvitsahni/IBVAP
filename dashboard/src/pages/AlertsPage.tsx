import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertFeed } from '@/components/alert/AlertFeed';
import { AlertDetailPanel } from '@/components/alert/AlertDetailPanel';
import { api } from '@/services/api';
import type { Alert as ApiAlert } from '@/types/api';

interface DashboardAlert {
  id: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  cameraId: string;
  timestamp: string;
  status: string;
}

function mapSeverity(threatScore: number): DashboardAlert['severity'] {
  if (threatScore >= 0.8) return 'critical';
  if (threatScore >= 0.6) return 'high';
  if (threatScore >= 0.4) return 'medium';
  if (threatScore >= 0.2) return 'low';
  return 'info';
}

function mapApiAlert(raw: ApiAlert): DashboardAlert {
  return {
    id: raw.alert_id || String(raw.id),
    type: raw.reason,
    severity: mapSeverity(raw.threat_score),
    cameraId: raw.camera_id,
    timestamp: raw.timestamp,
    status: raw.status,
  };
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getAlerts()
      .then((raw) => setAlerts(raw.map(mapApiAlert)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
      />
    </motion.div>
  );
}
