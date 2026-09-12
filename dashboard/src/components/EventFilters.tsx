import { Search } from 'lucide-react';

const DATE_RANGES = [
  { value: 'all', label: 'All time' },
  { value: '24h', label: 'Last 24h' },
  { value: '7d', label: 'Last 7 days' },
  { value: '14d', label: 'Last 14 days' },
];

export default function EventFilters({ filters, onChange, cameras, eventTypes }) {
  const update = (key, value) => onChange({ ...filters, [key]: value });

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div className="relative flex-1 min-w-[180px]">
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ops-muted" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => update('search', e.target.value)}
          placeholder="Search event ID, camera, type…"
          className="w-full rounded-md border border-ops-border bg-ops-bg py-1.5 pl-8 pr-3 text-xs text-ops-text placeholder:text-ops-muted/60 outline-none focus:border-ops-accent focus:ring-1 focus:ring-ops-accent transition-colors"
        />
      </div>

      <select
        value={filters.cameraId}
        onChange={(e) => update('cameraId', e.target.value)}
        className="rounded-md border border-ops-border bg-ops-bg px-2.5 py-1.5 text-xs text-ops-text outline-none focus:border-ops-accent transition-colors"
      >
        <option value="all">All cameras</option>
        {cameras.map((c) => (
          <option key={c.id} value={c.id}>
            {c.id}
          </option>
        ))}
      </select>

      <select
        value={filters.type}
        onChange={(e) => update('type', e.target.value)}
        className="rounded-md border border-ops-border bg-ops-bg px-2.5 py-1.5 text-xs text-ops-text outline-none focus:border-ops-accent transition-colors"
      >
        <option value="all">All event types</option>
        {eventTypes.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <select
        value={filters.range}
        onChange={(e) => update('range', e.target.value)}
        className="rounded-md border border-ops-border bg-ops-bg px-2.5 py-1.5 text-xs text-ops-text outline-none focus:border-ops-accent transition-colors"
      >
        {DATE_RANGES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
    </div>
  );
}
