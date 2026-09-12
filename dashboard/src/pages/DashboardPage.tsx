import { useEffect, useRef, useState } from 'react';
import { Camera, Video, VideoOff, AlertTriangle } from 'lucide-react';
import Sidebar from '../components/layout/Sidebar';
import TopBar from '../components/layout/TopBar';
import StatCard from '../components/ui/StatCard';
import CameraGrid from '../components/CameraGrid';
import AlertFeed from '../components/AlertFeed';
import AlertDetailPanel from '../components/AlertDetailPanel';
import ConnectionStatus from '../components/ConnectionStatus';
import ToastStack from '../components/ToastStack';
import { CameraGridSkeleton, ListSkeleton } from '../components/Skeletons';
import { useAlertStream } from '../hooks/useAlertStream';
import { MOCK_CAMERAS, MOCK_ALERTS } from '../data/mockData';

export default function DashboardPage() {
  const { alerts, connectionStatus, updateAlertStatus } = useAlertStream({
    initialAlerts: MOCK_ALERTS,
    intervalMs: 15000,
  });
  const [selectedAlertId, setSelectedAlertId] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const knownAlertIds = useRef(new Set(MOCK_ALERTS.map((a) => a.id)));

  useEffect(() => {
    const timer = setTimeout(() => setInitialLoading(false), 700);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const fresh = alerts.filter((a) => !knownAlertIds.current.has(a.id));
    if (fresh.length === 0) return;
    fresh.forEach((a) => knownAlertIds.current.add(a.id));
    setToasts((prev) => [...fresh, ...prev].slice(0, 4));
  }, [alerts]);

  const dismissToast = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const onlineCount = MOCK_CAMERAS.filter((c) => c.status === 'online').length;
  const offlineCount = MOCK_CAMERAS.filter((c) => c.status === 'offline').length;
  const activeAlertCount = alerts.filter((a) => a.status === 'new').length;
  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  return (
    <div className="flex h-screen bg-surface-bg font-sans">
      <Sidebar badgeCounts={{ alerts: activeAlertCount }} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar alertCount={activeAlertCount} />

        <main className="flex-1 overflow-y-auto p-5">
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard icon={Camera} label="Total Cameras" value={MOCK_CAMERAS.length} tone="primary" />
            <StatCard icon={Video} label="Online" value={onlineCount} tone="success" />
            <StatCard icon={VideoOff} label="Offline" value={offlineCount} tone="muted" />
            <StatCard icon={AlertTriangle} label="Active Alerts" value={activeAlertCount} tone="danger" />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
            <div className="min-w-0">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-surface-text">Live Camera Feeds</h2>
                <ConnectionStatus status={connectionStatus} />
              </div>
              {initialLoading ? <CameraGridSkeleton /> : <CameraGrid cameras={MOCK_CAMERAS} />}
            </div>

            <div className="min-h-[320px]">
              {initialLoading ? (
                <div className="rounded-lg border border-surface-border bg-white shadow-card">
                  <ListSkeleton />
                </div>
              ) : (
                <AlertFeed alerts={alerts} onSelectAlert={(a) => setSelectedAlertId(a.id)} />
              )}
            </div>
          </div>
        </main>
      </div>

      {selectedAlert && (
        <AlertDetailPanel
          alert={selectedAlert}
          onClose={() => setSelectedAlertId(null)}
          onUpdateStatus={updateAlertStatus}
        />
      )}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
