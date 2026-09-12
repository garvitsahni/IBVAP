const STATUS_CONFIG = {
  connecting: { label: 'Connecting…', dot: 'bg-ops-muted', pulse: false },
  live: { label: 'Live', dot: 'bg-severity-low', pulse: true },
  reconnecting: { label: 'Reconnecting…', dot: 'bg-severity-medium', pulse: true },
};

export default function ConnectionStatus({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.connecting;

  return (
    <span className="flex items-center gap-1.5 text-[11px] text-ops-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot} ${config.pulse ? 'animate-pulse' : ''}`} />
      {config.label}
    </span>
  );
}
