const STATUS_CONFIG: Record<string, { label: string; color: string; pulse: boolean }> = {
  connecting: { label: 'Connecting\u2026', color: 'bg-text-muted', pulse: false },
  live: { label: 'Live', color: 'bg-status-online', pulse: false },
  reconnecting: { label: 'Reconnecting\u2026', color: 'bg-status-degraded', pulse: true },
  disconnected: { label: 'Offline', color: 'bg-status-offline', pulse: false },
};

interface ConnectionStatusProps {
  status: string;
}

export default function ConnectionStatus({ status }: ConnectionStatusProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.connecting;

  return (
    <span className="flex items-center gap-1.5 text-[11px] text-text-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${config.color} ${config.pulse ? 'animate-pulse' : ''}`} />
      {config.label}
    </span>
  );
}
