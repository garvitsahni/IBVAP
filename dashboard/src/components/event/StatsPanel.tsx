interface Event {
  cameraId: string;
  severity: string;
  status: string;
}

interface StatsPanelProps {
  events: Event[];
}

function BarChartSimple({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="space-y-1">
      {data.map(d => (
        <div key={d.label} className="flex items-center gap-2 text-xs">
          <span className="w-20 truncate text-text-muted">{d.label}</span>
          <div className="flex-1 h-4 bg-surface-2 rounded overflow-hidden">
            <div
              className="h-full bg-accent/60 rounded"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <span className="w-8 text-right font-mono text-text-muted">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function StatsPanel({ events }: StatsPanelProps) {
  const detectionsByCamera = Object.values(
    events.reduce((acc, e) => {
      acc[e.cameraId] = acc[e.cameraId] || { label: e.cameraId, value: 0 };
      acc[e.cameraId].value += 1;
      return acc;
    }, {} as Record<string, { label: string; value: number }>)
  ).sort((a, b) => b.value - a.value);

  const falsePositives = events.filter((e) => e.status === 'false_positive').length;
  const falsePositiveRate = events.length ? Math.round((falsePositives / events.length) * 100) : 0;
  const critical = events.filter((e) => e.severity === 'critical').length;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <StatCard label="Total Events" value={events.length} />
        <StatCard label="Critical" value={critical} />
        <StatCard label="FP Rate" value={`${falsePositiveRate}%`} />
      </div>

      <div className="rounded-md border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-medium uppercase tracking-wider text-text-muted">By Camera</h3>
        {detectionsByCamera.length === 0 ? (
          <p className="text-xs text-text-muted">No events in range.</p>
        ) : (
          <BarChartSimple data={detectionsByCamera} />
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted">{label}</p>
      <p className="font-display text-xl font-semibold text-text-primary">{value}</p>
    </div>
  );
}
