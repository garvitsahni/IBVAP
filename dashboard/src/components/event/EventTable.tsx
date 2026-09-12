import { StatusBadge } from '@/components/ui/StatusBadge';
import EmptyState from '@/components/EmptyState';

interface Event {
  id: string;
  cameraId: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  status: string;
  timestamp: number;
}

interface EventTableProps {
  events: Event[];
  onSelectEvent?: (event: Event) => void;
}

const STATUS_LABEL: Record<string, string> = {
  acknowledged: 'Acknowledged',
  escalated: 'Escalated',
  false_positive: 'False Positive',
  resolved: 'Resolved',
  new: 'New',
};

function formatDateTime(ts: number) {
  return new Date(ts).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function EventTable({ events, onSelectEvent }: EventTableProps) {
  return (
    <div className="overflow-hidden rounded-md border border-border">
      <div className="max-h-[480px] overflow-y-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-surface-2 text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Event</th>
              <th className="px-3 py-2 font-medium">Camera</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Severity</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {events.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    title="No events match the current filters"
                    description="Try widening the date range or clearing a filter."
                  />
                </td>
              </tr>
            ) : (
              events.map((event) => (
                <tr
                  key={event.id}
                  onClick={() => onSelectEvent?.(event)}
                  className="cursor-pointer bg-surface hover:bg-surface-2 transition-colors"
                >
                  <td className="px-3 py-2 font-mono text-text">{event.id}</td>
                  <td className="px-3 py-2 font-mono text-text-muted">{event.cameraId}</td>
                  <td className="px-3 py-2 text-text">{event.type}</td>
                  <td className="px-3 py-2">
                    <StatusBadge severity={event.severity} />
                  </td>
                  <td className="px-3 py-2 text-text-muted">{STATUS_LABEL[event.status] || event.status}</td>
                  <td className="px-3 py-2 text-text-muted">{formatDateTime(event.timestamp)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border bg-surface-2 px-3 py-1.5 text-[11px] text-text-muted">
        {events.length} event{events.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
