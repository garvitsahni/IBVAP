import AlertItem from './AlertItem';
import EmptyState from './EmptyState';

export default function AlertFeed({ alerts, onSelectAlert }) {
  return (
    <div className="flex h-full flex-col rounded-lg border border-surface-border bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-surface-border px-3.5 py-3">
        <h2 className="text-sm font-semibold text-surface-text">Recent Alerts</h2>
        <button type="button" className="text-xs font-medium text-brand-primary hover:underline">
          View All →
        </button>
      </div>

      <div className="flex-1 divide-y divide-surface-border overflow-y-auto">
        {alerts.length === 0 ? (
          <EmptyState title="No alerts in the current window" />
        ) : (
          alerts
            .slice()
            .sort((a, b) => b.timestamp - a.timestamp)
            .map((alert) => <AlertItem key={alert.id} alert={alert} onSelect={onSelectAlert} />)
        )}
      </div>
    </div>
  );
}
