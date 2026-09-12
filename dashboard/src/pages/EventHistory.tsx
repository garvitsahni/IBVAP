import { useMemo, useState } from 'react';
import EventFilters from '../components/EventFilters';
import EventTable from '../components/EventTable';
import StatsPanel from '../components/StatsPanel';
import AlertDetailPanel from '../components/AlertDetailPanel';
// TODO: Replace with real API (Task 10)
const MOCK_CAMERAS: Array<{ id: string; label: string; status: string }> = [];
const MOCK_EVENTS: Array<{ id: string; cameraId: string; type: string; timestamp: number; status: string }> = [];

const RANGE_MS = {
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '14d': 14 * 24 * 60 * 60 * 1000,
};

export default function EventHistoryPage() {
  const [events, setEvents] = useState(MOCK_EVENTS);
  const [filters, setFilters] = useState({ search: '', cameraId: 'all', type: 'all', range: 'all' });
  const [selectedEventId, setSelectedEventId] = useState(null);

  const eventTypes = useMemo(() => [...new Set(MOCK_EVENTS.map((e) => e.type))], []);

  const filteredEvents = useMemo(() => {
    const now = Date.now();
    return events.filter((e) => {
      if (filters.cameraId !== 'all' && e.cameraId !== filters.cameraId) return false;
      if (filters.type !== 'all' && e.type !== filters.type) return false;
      if (filters.range !== 'all' && now - e.timestamp > RANGE_MS[filters.range]) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const haystack = `${e.id} ${e.cameraId} ${e.type}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [events, filters]);

  const selectedEvent = events.find((e) => e.id === selectedEventId) || null;

  const handleUpdateStatus = (eventId, nextStatus) => {
    setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, status: nextStatus } : e)));
  };

  return (
    <div className="flex min-h-screen flex-col gap-4 bg-ops-bg p-4 font-sans">
      <div>
        <h1 className="text-sm font-semibold text-ops-text">Event History &amp; Analytics</h1>
        <p className="text-xs text-ops-muted">Past detections across all cameras</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-3 min-w-0">
          <EventFilters
            filters={filters}
            onChange={setFilters}
            cameras={MOCK_CAMERAS}
            eventTypes={eventTypes}
          />
          <EventTable events={filteredEvents} onSelectEvent={(e) => setSelectedEventId(e.id)} />
        </div>

        <StatsPanel events={filteredEvents} />
      </div>

      {selectedEvent && (
        <AlertDetailPanel
          alert={selectedEvent}
          onClose={() => setSelectedEventId(null)}
          onUpdateStatus={handleUpdateStatus}
        />
      )}
    </div>
  );
}
