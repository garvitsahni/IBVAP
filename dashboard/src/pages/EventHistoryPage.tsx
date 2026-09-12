import { useMemo, useState, useEffect } from 'react';
import EventFilters from '@/components/EventFilters';
import EventTable from '@/components/event/EventTable';
import StatsPanel from '@/components/event/StatsPanel';
import { AlertDetailPanel } from '@/components/alert/AlertDetailPanel';
import { api } from '@/services/api';
import type { DetectionEvent } from '@/types/api';

interface HistoryEvent {
  id: string;
  cameraId: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status: string;
  timestamp: number;
}

function mapSeverity(confidence: number): HistoryEvent['severity'] {
  if (confidence >= 0.8) return 'critical';
  if (confidence >= 0.6) return 'high';
  if (confidence >= 0.4) return 'medium';
  if (confidence >= 0.2) return 'low';
  return 'info';
}

function mapDetection(raw: DetectionEvent): HistoryEvent {
  return {
    id: String(raw.id),
    cameraId: raw.camera_id,
    type: raw.object_type,
    severity: mapSeverity(raw.confidence),
    status: 'new',
    timestamp: new Date(raw.timestamp).getTime(),
  };
}

const RANGE_MS: Record<string, number> = {
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '14d': 14 * 24 * 60 * 60 * 1000,
};

export function EventHistoryPage() {
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [filters, setFilters] = useState({ search: '', cameraId: 'all', type: 'all', range: 'all' });
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getDetections(undefined, 100)
      .then((raw) => setEvents(raw.map(mapDetection)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const eventTypes = useMemo(() => [...new Set(events.map((e) => e.type))], [events]);

  const filteredEvents = useMemo(() => {
    const now = Date.now();
    return events.filter((e) => {
      if (filters.cameraId !== 'all' && e.cameraId !== filters.cameraId) return false;
      if (filters.type !== 'all' && e.type !== filters.type) return false;
      if (filters.range !== 'all' && now - e.timestamp > (RANGE_MS[filters.range] ?? Infinity)) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const haystack = `${e.id} ${e.cameraId} ${e.type}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [events, filters]);

  const selectedEvent = events.find((e) => e.id === selectedEventId) || null;

  const handleUpdateStatus = (eventId: string, nextStatus: string) => {
    setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, status: nextStatus } : e)));
  };

  const camerasForFilter = useMemo(() => {
    const unique = [...new Set(events.map((e) => e.cameraId))];
    return unique.map((id) => ({ id, label: id, status: 'active' }));
  }, [events]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Event History</h1>
        <p className="text-sm text-text-secondary">Past detections across all cameras</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-3 min-w-0">
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded bg-surface-2" />
              ))}
            </div>
          ) : (
            <>
              <EventFilters
                filters={filters}
                onChange={setFilters}
                cameras={camerasForFilter}
                eventTypes={eventTypes}
              />
              <EventTable events={filteredEvents} onSelectEvent={(e) => setSelectedEventId(e.id)} />
            </>
          )}
        </div>

        <StatsPanel events={filteredEvents} />
      </div>

      <AlertDetailPanel
        alert={selectedEvent as unknown as Record<string, unknown> | null}
        onClose={() => setSelectedEventId(null)}
      />
    </div>
  );
}
