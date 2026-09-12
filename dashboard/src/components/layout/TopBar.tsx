import { Search, Bell, ShieldCheck } from 'lucide-react';

export default function TopBar({ alertCount = 0 }) {
  const now = new Date();
  const dateLabel = now.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
  const timeLabel = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

  return (
    <header className="flex items-center justify-between border-b border-surface-border bg-white px-5 py-3">
      <div className="relative w-full max-w-md">
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-surface-muted" />
        <input
          type="text"
          placeholder="Search cameras, locations…"
          className="w-full rounded-lg border border-surface-border bg-surface-bg py-2 pl-9 pr-3 text-sm text-surface-text placeholder:text-surface-muted outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-colors"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          className="relative rounded-full p-2 text-surface-muted transition-colors hover:bg-surface-bg hover:text-surface-text"
          aria-label="Notifications"
        >
          <Bell size={18} />
          {alertCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-severity-critical px-1 text-[9px] font-medium text-white">
              {alertCount}
            </span>
          )}
        </button>

        <div className="flex items-center gap-2 border-l border-surface-border pl-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-primary/10 text-brand-primary">
            <ShieldCheck size={14} />
          </div>
          <div className="leading-tight">
            <p className="text-xs font-medium text-surface-text">Ministry of Home Affairs</p>
            <p className="text-[10px] text-surface-muted">
              {dateLabel}, {timeLabel}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
