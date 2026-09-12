import { useState, useEffect } from 'react';
import { Search, Bell, ShieldCheck } from 'lucide-react';

export function TopBar({ alertCount = 0 }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const dateLabel = time.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  const timeLabel = time.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-5 py-3">
      <div className="relative w-full max-w-md">
        <Search
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary"
        />
        <input
          type="text"
          placeholder="Search cameras, locations…"
          className="w-full rounded-lg border border-border bg-bg py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-secondary outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          className="relative rounded-full p-2 text-text-secondary transition-colors hover:bg-accent/10 hover:text-text-primary"
          aria-label="Notifications"
        >
          <Bell size={18} />
          {alertCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-medium text-white">
              {alertCount}
            </span>
          )}
        </button>

        <div className="flex items-center gap-2 border-l border-border pl-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/10 text-accent">
            <ShieldCheck size={14} />
          </div>
          <div className="leading-tight">
            <p className="text-xs font-medium text-text-primary">Ministry of Home Affairs</p>
            <p className="text-[10px] text-text-secondary">
              {dateLabel}, {timeLabel}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
