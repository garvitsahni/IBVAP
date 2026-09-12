const STATUS_CONFIG: Record<string, { label: string; dot: string; pulse: boolean }> = {
  connecting: { label: 'Connecting\u2026', dot: 'bg-text-muted', pulse: false },
  live: { label: 'Live', dot: 'bg-status-online', pulse: true },
  reconnecting: { label: 'Reconnecting\u2026', dot: 'bg-status-degraded', pulse: true },
};

interface ConnectionStatusProps {
  status: string;
}

export default function ConnectionStatus({ status }: ConnectionStatusProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.connecting;

  return (
    <span className="flex items-center gap-1.5 text-[11px] text-text-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot} ${config.pulse ? 'animate-pulse' : ''}`} />
      {config.label}
    </span>
  );
}
