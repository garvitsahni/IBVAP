// The API serves naive-UTC ISO strings (datetime.utcnow().isoformat()).
// new Date() would parse those as local time and skew every displayed time,
// so we normalize to a real UTC instant before formatting.
export function parseTs(value: string | null | undefined): Date | null {
  if (!value) return null;
  const hasZone = value.includes("Z") || /[+-]\d{2}:\d{2}$/.test(value);
  const d = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatTime(value: string | null | undefined): string {
  const d = parseTs(value);
  return d ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
}

export function formatRelative(value: string | null | undefined): string {
  const d = parseTs(value);
  if (!d) return "—";
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function secondsSince(value: string | null | undefined): number | null {
  const d = parseTs(value);
  if (!d) return null;
  return (Date.now() - d.getTime()) / 1000;
}
