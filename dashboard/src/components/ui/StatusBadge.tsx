const SEVERITY_STYLES = {
  critical: 'bg-severity-critical/10 text-severity-critical',
  high: 'bg-severity-critical/10 text-severity-critical',
  medium: 'bg-severity-medium/15 text-yellow-700',
  low: 'bg-severity-low/10 text-green-700',
  info: 'bg-severity-info/10 text-severity-info',
};

const SEVERITY_LABEL = {
  critical: 'High',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

export default function StatusBadge({ severity }) {
  const style = SEVERITY_STYLES[severity] || 'bg-surface-border text-surface-muted';
  const label = SEVERITY_LABEL[severity] || severity;

  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${style}`}>
      {label}
    </span>
  );
}
