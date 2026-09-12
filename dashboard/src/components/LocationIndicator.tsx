import { MapPin } from 'lucide-react';

// Lightweight placeholder — swap the grid surface for an actual map
// (Leaflet/Mapbox) later; lat/lng are already in the shape it'll need.
export default function LocationIndicator({ location }) {
  if (!location) return null;

  return (
    <div className="rounded-md border border-ops-border bg-ops-bg p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-ops-muted">
        <MapPin size={13} />
        Location
      </div>

      <div
        className="relative mb-2 h-24 w-full overflow-hidden rounded border border-ops-border"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)',
          backgroundSize: '16px 16px',
          backgroundColor: '#0B0E11',
        }}
      >
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-severity-critical/60" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-severity-critical" />
          </span>
        </div>
      </div>

      <p className="text-sm text-ops-text">{location.label}</p>
      <p className="font-mono text-[11px] text-ops-muted">
        {location.lat.toFixed(4)}, {location.lng.toFixed(4)}
      </p>
    </div>
  );
}
