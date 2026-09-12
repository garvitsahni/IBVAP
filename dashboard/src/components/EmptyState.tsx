import { Inbox, AlertOctagon } from 'lucide-react';

// One shared empty/error block so every list/grid in the app (camera grid,
// alert feed, event table) reads the same way instead of each rolling its own.
export default function EmptyState({ variant = 'empty', title, description }) {
  const isError = variant === 'error';
  const Icon = isError ? AlertOctagon : Inbox;

  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <Icon size={20} className={isError ? 'text-severity-critical' : 'text-ops-muted'} />
      <p className="text-xs font-medium text-ops-text">{title}</p>
      {description && <p className="max-w-xs text-[11px] text-ops-muted">{description}</p>}
    </div>
  );
}
