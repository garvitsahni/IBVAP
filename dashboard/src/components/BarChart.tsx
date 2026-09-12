// Simple horizontal bar chart built with plain divs — no chart library
// dependency for something this small. Swap for recharts later if the
// analytics view grows more complex.

export default function BarChart({ data, valueSuffix = '' }) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-2">
          <span className="w-16 shrink-0 truncate font-mono text-[11px] text-ops-muted">{d.label}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-ops-bg">
            <div
              className="h-full rounded-full bg-ops-accent"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-[11px] text-ops-text">
            {d.value}
            {valueSuffix}
          </span>
        </div>
      ))}
    </div>
  );
}
