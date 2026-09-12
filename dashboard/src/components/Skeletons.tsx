export function CameraGridSkeleton({ count = 8 }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="aspect-video animate-pulse rounded-md border border-ops-border bg-ops-panel" />
      ))}
    </div>
  );
}

export function ListSkeleton({ count = 5 }) {
  return (
    <div className="divide-y divide-ops-border">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-pulse px-3 py-2.5">
          <div className="mb-2 h-3 w-3/4 rounded bg-ops-border" />
          <div className="h-2.5 w-1/3 rounded bg-ops-border/70" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 6, columns = 6 }) {
  return (
    <div className="divide-y divide-ops-border">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex animate-pulse gap-4 px-3 py-2.5">
          {Array.from({ length: columns }).map((__, c) => (
            <div key={c} className="h-2.5 flex-1 rounded bg-ops-border/70" />
          ))}
        </div>
      ))}
    </div>
  );
}
