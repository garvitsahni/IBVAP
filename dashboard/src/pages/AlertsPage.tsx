import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertFeed } from '@/components/alert/AlertFeed';
import { AlertDetailColumn } from '@/components/alert/AlertDetailColumn';
import { api } from '@/services/api';
import { useSSE } from '@/hooks/useSSE';
import { mapApiAlert, isOpenStatus, type FeedAlert, type Severity } from '@/lib/alerts';
import type { Alert as ApiAlert } from '@/types/api';

type SeverityFilter = 'all' | Severity;
type StatusFilter = 'all' | 'open' | 'acknowledged';

const SEVERITIES: SeverityFilter[] = ['all', 'critical', 'high', 'medium', 'low', 'info'];

interface AlertsPageProps {
  initialSelectedId?: string | null;
}

export function AlertsPage({ initialSelectedId = null }: AlertsPageProps) {
  const [alerts, setAlerts] = useState<FeedAlert[]>([]);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(initialSelectedId);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('open');

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
      const mapped = mapApiAlert(data as unknown as ApiAlert);
      setAlerts((prev) => [mapped, ...prev]);
      setSelectedAlertId(mapped.id); // newest becomes selection
    });
  }, [on]);

  // Newest auto-selected when none selected (initialSelectedId from nav may miss if list still loading)
  useEffect(() => {
    if (!selectedAlertId && alerts.length > 0) {
      setSelectedAlertId(alerts[0].id);
    }
  }, [alerts, selectedAlertId]);

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { all: alerts.length, critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    for (const a of alerts) counts[a.severity] = (counts[a.severity] || 0) + 1;
    return counts;
  }, [alerts]);

  const filtered = useMemo(() => {
    return alerts.filter((a) => {
      if (severityFilter !== 'all' && a.severity !== severityFilter) return false;
      if (statusFilter === 'open' && !isOpenStatus(a.status)) return false;
      if (statusFilter === 'acknowledged' && a.status !== 'acknowledged') return false;
      return true;
    });
  }, [alerts, severityFilter, statusFilter]);

  const selectedAlert = alerts.find((a) => a.id === selectedAlertId) || null;

  const handleChanged = (updated: FeedAlert) => {
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };

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

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverityFilter(s)}
            className={
              severityFilter === s
                ? 'rounded-full border border-accent bg-accent/10 px-3 py-1 text-[11px] font-medium text-accent'
                : 'rounded-full border border-border px-3 py-1 text-[11px] font-medium text-text-muted hover:bg-surface-2'
            }
          >
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="ml-1.5 font-mono opacity-70">{severityCounts[s] ?? 0}</span>
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        {(['all', 'open', 'acknowledged'] as StatusFilter[]).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={
              statusFilter === s
                ? 'rounded-full border border-accent bg-accent/10 px-3 py-1 text-[11px] font-medium text-accent'
                : 'rounded-full border border-border px-3 py-1 text-[11px] font-medium text-text-muted hover:bg-surface-2'
            }
          >
            {s === 'all' ? 'All statuses' : s === 'open' ? 'Open' : 'Acknowledged'}
          </button>
        ))}
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
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="min-w-0">
            <AlertFeed
              alerts={filtered}
              selectedId={selectedAlertId ?? undefined}
              onSelect={(a) => setSelectedAlertId(a.id)}
            />
          </div>
          <div className="min-w-0">
            <AlertDetailColumn alert={selectedAlert} onChanged={handleChanged} />
          </div>
        </div>
      )}
    </motion.div>
  );
}
