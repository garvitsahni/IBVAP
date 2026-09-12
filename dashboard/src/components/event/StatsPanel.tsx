import BarChart from '@/components/BarChart';
import { NumberTicker } from '@/registry/magicui/number-ticker';

interface Event {
  cameraId: string;
  severity: string;
  status: string;
}

interface StatsPanelProps {
  events: Event[];
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
        <StatCard label="Total Events">
          <NumberTicker value={events.length} className="text-2xl font-bold text-text" />
        </StatCard>
        <StatCard label="Critical">
          <NumberTicker value={critical} className="text-2xl font-bold text-severity-critical" />
        </StatCard>
        <StatCard label="False Positive Rate">
          <NumberTicker value={falsePositiveRate} className="text-2xl font-bold text-severity-medium" />
          <span className="text-2xl font-bold text-severity-medium">%</span>
        </StatCard>
      </div>

      <div className="rounded-md border border-border bg-surface p-3">
        <h3 className="mb-3 text-xs font-medium text-text-muted">Detections per Camera</h3>
        {detectionsByCamera.length === 0 ? (
          <p className="text-xs text-text-muted">No events in range.</p>
        ) : (
          <BarChart data={detectionsByCamera} />
        )}
      </div>
    </div>
  );
}

function StatCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="mb-1 text-[10px] text-text-muted">{label}</p>
      <div className="flex items-baseline gap-0.5">{children}</div>
    </div>
  );
}
