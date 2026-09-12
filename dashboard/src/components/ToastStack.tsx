import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

const SEVERITY_ACCENT = {
  critical: 'border-l-severity-critical',
  high: 'border-l-severity-high',
  medium: 'border-l-severity-medium',
  low: 'border-l-severity-low',
  info: 'border-l-severity-info',
};

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      role="status"
      className={`w-72 rounded-md border border-ops-border ${SEVERITY_ACCENT[toast.severity] || 'border-l-ops-border'} border-l-2 bg-ops-panel2 shadow-panel px-3 py-2.5 transition-all duration-200`}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-ops-muted" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-ops-text">New alert — {toast.type}</p>
          <p className="text-[11px] text-ops-muted">{toast.cameraId}</p>
        </div>
      </div>
    </div>
  );
}

export default function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
