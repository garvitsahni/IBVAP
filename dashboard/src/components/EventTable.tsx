import StatusBadge from './ui/StatusBadge';
import EmptyState from './EmptyState';

const STATUS_LABEL = {
  acknowledged: 'Acknowledged',
  escalated: 'Escalated',
  false_positive: 'False Positive',
  resolved: 'Resolved',
  new: 'New',
};

function formatDateTime(ts) {
  return new Date(ts).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function EventTable({ events, onSelectEvent }) {
  return (
    <div className="overflow-hidden rounded-md border border-ops-border">
      <div className="max-h-[480px] overflow-y-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-ops-panel2 text-ops-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Event</th>
              <th className="px-3 py-2 font-medium">Camera</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Severity</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ops-border">
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
                  className="cursor-pointer bg-ops-panel hover:bg-ops-panel2 transition-colors"
                >
                  <td className="px-3 py-2 font-mono text-ops-text">{event.id}</td>
                  <td className="px-3 py-2 font-mono text-ops-muted">{event.cameraId}</td>
                  <td className="px-3 py-2 text-ops-text">{event.type}</td>
                  <td className="px-3 py-2">
                    <StatusBadge severity={event.severity} />
                  </td>
                  <td className="px-3 py-2 text-ops-muted">{STATUS_LABEL[event.status] || event.status}</td>
                  <td className="px-3 py-2 text-ops-muted">{formatDateTime(event.timestamp)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="border-t border-ops-border bg-ops-panel2 px-3 py-1.5 text-[11px] text-ops-muted">
        {events.length} event{events.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
