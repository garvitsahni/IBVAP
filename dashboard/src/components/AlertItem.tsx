import { AlertTriangle } from 'lucide-react';

// Assumes a shared StatusBadge component from Phase 1 (severity-colored pill).
// If its prop name differs from `severity`, adjust the import/usage below —
// the rest of this file doesn't depend on its internals.
import StatusBadge from './ui/StatusBadge';

function timeAgo(timestamp) {
  const diffMs = Date.now() - timestamp;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

const SEVERITY_BORDER = {
  critical: 'border-l-severity-critical',
  high: 'border-l-severity-high',
  medium: 'border-l-severity-medium',
  low: 'border-l-severity-low',
  info: 'border-l-severity-info',
};

export default function AlertItem({ alert, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(alert)}
      className={`w-full text-left border-l-2 ${SEVERITY_BORDER[alert.severity] || 'border-l-ops-border'} bg-ops-panel hover:bg-ops-panel2 transition-colors px-3 py-2.5 flex flex-col gap-1`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          {alert.severity === 'critical' && (
            <AlertTriangle size={12} className="shrink-0 text-severity-critical" />
          )}
          <span className="truncate text-sm text-ops-text">{alert.type}</span>
        </span>
        <StatusBadge severity={alert.severity} />
      </div>
      <div className="flex items-center justify-between text-[11px] text-ops-muted">
        <span className="font-mono">{alert.cameraId}</span>
        <span>{timeAgo(alert.timestamp)}</span>
      </div>
    </button>
  );
}
