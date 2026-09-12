import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Camera, Video, VideoOff, AlertTriangle } from 'lucide-react';
import { StatCard } from '@/components/ui/StatCard';
import CameraGrid from '@/components/camera/CameraGrid';
import { AlertFeed } from '@/components/alert/AlertFeed';
import { AlertDetailPanel } from '@/components/alert/AlertDetailPanel';
import ConnectionStatus from '@/components/event/ConnectionStatus';
import { ToastStack } from '@/components/alert/ToastStack';
import { SSEClient } from '@/services/sse';
import { api } from '@/services/api';
import type { Alert as ApiAlert, Camera as ApiCamera } from '@/types/api';

interface DashboardAlert {
  id: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  cameraId: string;
  timestamp: string;
  status: string;
}

interface DashboardCamera {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'degraded';
  lastSeen?: string;
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

function mapApiCamera(raw: ApiCamera): DashboardCamera {
  return {
    id: raw.camera_id,
    name: raw.name,
    status: (raw.is_active ? raw.status : 'offline') as 'online' | 'offline' | 'degraded',
    lastSeen: raw.last_seen,
  };
}

export function DashboardPage() {
  const [cameras, setCameras] = useState<DashboardCamera[]>([]);
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<DashboardAlert[]>([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [initialLoading, setInitialLoading] = useState(true);
  const knownAlertIds = useRef(new Set<string>());

  useEffect(() => {
    Promise.all([
      api.getCameras().catch(() => []),
      api.getAlerts().catch(() => []),
    ]).then(([rawCameras, rawAlerts]) => {
      setCameras(rawCameras.map(mapApiCamera));
      const mapped = rawAlerts.map(mapApiAlert);
      setAlerts(mapped);
      mapped.forEach((a) => knownAlertIds.current.add(a.id));
      setInitialLoading(false);
    });
  }, []);

  useEffect(() => {
    const client = new SSEClient();
    client.connect('/api/v1/alerts/stream');

    client.on('alert_fired', (data) => {
      setConnectionStatus('live');
      const alert = mapApiAlert(data as unknown as ApiAlert);
      setAlerts((prev) => [alert, ...prev].slice(0, 50));
      if (!knownAlertIds.current.has(alert.id)) {
        knownAlertIds.current.add(alert.id);
        setToasts((prev) => [alert, ...prev].slice(0, 4));
      }
    });

    client.on('alert_enriched', (data) => {
      const enriched = data as unknown as ApiAlert;
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === enriched.alert_id
            ? { ...a, type: enriched.reason || a.type }
            : a
        )
      );
    });

    setConnectionStatus('live');

    return () => {
      client.disconnect();
      setConnectionStatus('disconnected');
    };
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const onlineCount = cameras.filter((c) => c.status === 'online').length;
  const offlineCount = cameras.filter((c) => c.status === 'offline').length;
  const activeAlertCount = alerts.filter((a) => a.status === 'fired').length;
  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={Camera} label="Total Cameras" value={cameras.length} tone="primary" />
        <StatCard icon={Video} label="Online" value={onlineCount} tone="success" />
        <StatCard icon={VideoOff} label="Offline" value={offlineCount} tone="muted" />
        <StatCard icon={AlertTriangle} label="Active Alerts" value={activeAlertCount} tone="danger" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">Live Camera Feeds</h2>
            <ConnectionStatus status={connectionStatus} />
          </div>
          {initialLoading ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="aspect-video animate-pulse rounded-md border border-border bg-surface-2" />
              ))}
            </div>
          ) : (
            <CameraGrid cameras={cameras} />
          )}
        </div>

        <div className="min-h-[320px]">
          {initialLoading ? (
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="animate-pulse space-y-2">
                    <div className="h-3 w-3/4 rounded bg-surface-2" />
                    <div className="h-2.5 w-1/3 rounded bg-surface-2" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <AlertFeed
              alerts={alerts}
              selectedId={selectedAlertId ?? undefined}
              onSelect={(a) => setSelectedAlertId(a.id)}
            />
          )}
        </div>
      </div>

      <AlertDetailPanel
        alert={selectedAlert}
        onClose={() => setSelectedAlertId(null)}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </motion.div>
  );
}
