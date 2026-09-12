import BarChart from './BarChart';

export default function StatsPanel({ events }) {
  const detectionsByCamera = Object.values(
    events.reduce((acc, e) => {
      acc[e.cameraId] = acc[e.cameraId] || { label: e.cameraId, value: 0 };
      acc[e.cameraId].value += 1;
      return acc;
    }, {})
  ).sort((a, b) => b.value - a.value);

  const falsePositives = events.filter((e) => e.status === 'false_positive').length;
  const falsePositiveRate = events.length ? Math.round((falsePositives / events.length) * 100) : 0;

  const critical = events.filter((e) => e.severity === 'critical').length;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <StatCard label="Total Events" value={events.length} />
        <StatCard label="Critical" value={critical} tone="text-severity-critical" />
        <StatCard label="False Positive Rate" value={`${falsePositiveRate}%`} tone="text-severity-medium" />
      </div>

      <div className="rounded-md border border-ops-border bg-ops-panel p-3">
        <h3 className="mb-3 text-xs font-medium text-ops-muted">Detections per Camera</h3>
        {detectionsByCamera.length === 0 ? (
          <p className="text-xs text-ops-muted">No events in range.</p>
        ) : (
          <BarChart data={detectionsByCamera} />
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, tone = 'text-ops-text' }) {
  return (
    <div className="rounded-md border border-ops-border bg-ops-panel p-3">
      <p className="mb-1 text-[10px] text-ops-muted">{label}</p>
      <p className={`text-lg font-semibold ${tone}`}>{value}</p>
    </div>
  );
}
