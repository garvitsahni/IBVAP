import { VideoOff } from 'lucide-react';

const STATUS_DOT = {
  online: 'bg-brand-secondary',
  degraded: 'bg-severity-medium',
  offline: 'bg-surface-muted',
};

const STATUS_LABEL = {
  online: 'Live',
  degraded: 'Degraded',
  offline: 'Offline',
};

export default function CameraTile({ camera }) {
  const isOffline = camera.status === 'offline';
  const timeLabel = new Date().toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

  return (
    <div className="overflow-hidden rounded-lg border border-surface-border bg-white shadow-card">
      <div className="relative aspect-video bg-surface-text/90">
        {isOffline ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 bg-surface-bg text-surface-muted">
            <VideoOff size={20} strokeWidth={1.5} />
            <span className="text-[11px]">Signal lost</span>
          </div>
        ) : (
          <div className="h-full w-full bg-gradient-to-br from-slate-700 to-slate-900" />
        )}

        <div className="absolute left-2 top-2 flex items-center gap-1 rounded bg-black/50 px-1.5 py-0.5">
          <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[camera.status]} ${camera.status === 'online' ? 'animate-pulse' : ''}`} />
          <span className="text-[10px] font-medium text-white">{STATUS_LABEL[camera.status]}</span>
        </div>
      </div>
      <div className="px-2.5 py-2">
        <p className="text-xs font-medium text-surface-text">{camera.id} | {camera.label}</p>
        <p className="text-[10px] text-surface-muted">{timeLabel}</p>
      </div>
    </div>
  );
}
