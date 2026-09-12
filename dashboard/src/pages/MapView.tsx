import { MapPin, Camera, ShieldCheck, Navigation } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Polygon, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Leaflet's default marker assets need explicit URLs when used with Vite.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const CAMERAS = [
  { id: 'CAM-01', name: 'North Gate', status: 'Online', position: [28.4595, 77.0266] },
  { id: 'CAM-02', name: 'Watch Tower A', status: 'Online', position: [28.4632, 77.0315] },
  { id: 'CAM-03', name: 'East Fence', status: 'Alert', position: [28.4558, 77.0342] },
  { id: 'CAM-04', name: 'Patrol Route 2', status: 'Online', position: [28.4518, 77.029] },
  { id: 'CAM-05', name: 'South Checkpoint', status: 'Offline', position: [28.4495, 77.023] },
];

const BORDER_ZONE = [
  [28.466, 77.019],
  [28.466, 77.040],
  [28.446, 77.040],
  [28.446, 77.019],
];

function cameraIcon(status) {
  const background =
    status === 'Alert' ? '#dc2626' : status === 'Offline' ? '#64748b' : '#2563eb';

  return L.divIcon({
    className: '',
    html: `<div style="width:38px;height:38px;border-radius:50%;background:${background};border:3px solid white;box-shadow:0 2px 10px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;color:white;font-size:17px;">📹</div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -18],
  });
}

export default function MapView() {
  const online = CAMERAS.filter((c) => c.status === 'Online').length;
  const alerts = CAMERAS.filter((c) => c.status === 'Alert').length;

  return (
    <div className="min-h-full bg-surface-bg p-5 text-surface-text">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <MapPin size={20} className="text-brand-primary" />
            <h1 className="text-xl font-semibold">Map View</h1>
          </div>
          <p className="mt-1 text-sm text-surface-muted">
            Monitor camera locations and border surveillance zones.
          </p>
        </div>

        <div className="flex gap-2 text-xs">
          <span className="rounded-lg border border-surface-border bg-white px-3 py-2">
            <b className="text-brand-primary">{online}</b> Online
          </span>
          <span className="rounded-lg border border-surface-border bg-white px-3 py-2">
            <b className="text-severity-critical">{alerts}</b> Alert
          </span>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
        <div className="overflow-hidden rounded-xl border border-surface-border bg-white shadow-card">
          <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Navigation size={16} className="text-brand-primary" />
              Border Surveillance Map
            </div>
            <span className="text-xs text-surface-muted">Live camera positions</span>
          </div>

          <div className="relative min-h-[560px] overflow-hidden">
            <MapContainer
              center={[28.4575, 77.028]}
              zoom={14}
              scrollWheelZoom
              className="h-[560px] w-full"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              <Polygon
                positions={BORDER_ZONE}
                pathOptions={{
                  color: '#2563eb',
                  fillColor: '#2563eb',
                  fillOpacity: 0.08,
                  weight: 2,
                  dashArray: '8 6',
                }}
              />

              {CAMERAS.map((camera) => (
                <Circle
                  key={`${camera.id}-coverage`}
                  center={camera.position}
                  radius={180}
                  pathOptions={{
                    color: camera.status === 'Alert' ? '#dc2626' : '#2563eb',
                    fillColor: camera.status === 'Alert' ? '#dc2626' : '#2563eb',
                    fillOpacity: 0.05,
                    weight: 1,
                  }}
                />
              ))}

              {CAMERAS.map((camera) => (
                <Marker key={camera.id} position={camera.position} icon={cameraIcon(camera.status)}>
                  <Popup>
                    <div className="min-w-[170px]">
                      <strong>{camera.id}</strong>
                      <div>{camera.name}</div>
                      <div
                        style={{
                          marginTop: 4,
                          fontWeight: 600,
                          color:
                            camera.status === 'Alert'
                              ? '#dc2626'
                              : camera.status === 'Offline'
                                ? '#64748b'
                                : '#16a34a',
                        }}
                      >
                        ● {camera.status}
                      </div>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>

            <div className="pointer-events-none absolute bottom-4 left-4 z-[1000] rounded-lg bg-white/95 px-3 py-2 text-xs shadow-lg">
              <div className="mb-1 font-semibold">Border Sector A</div>
              <div className="flex items-center gap-2 text-surface-muted">
                <ShieldCheck size={13} /> Secure perimeter
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-white shadow-card">
          <div className="border-b border-surface-border px-4 py-3">
            <h2 className="text-sm font-semibold">Camera Locations</h2>
            <p className="mt-1 text-xs text-surface-muted">{CAMERAS.length} registered cameras</p>
          </div>

          <div className="divide-y divide-surface-border">
            {CAMERAS.map((camera) => (
              <div key={camera.id} className="flex items-center gap-3 px-4 py-3">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full ${
                    camera.status === 'Alert'
                      ? 'bg-severity-critical/10 text-severity-critical'
                      : camera.status === 'Offline'
                        ? 'bg-surface-muted/10 text-surface-muted'
                        : 'bg-brand-primary/10 text-brand-primary'
                  }`}
                >
                  <Camera size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{camera.name}</p>
                  <p className="font-mono text-[11px] text-surface-muted">{camera.id}</p>
                </div>
                <span
                  className={`text-[11px] font-medium ${
                    camera.status === 'Alert'
                      ? 'text-severity-critical'
                      : camera.status === 'Offline'
                        ? 'text-surface-muted'
                        : 'text-brand-primary'
                  }`}
                >
                  {camera.status}
                </span>
              </div>
            ))}
          </div>

          <div className="border-t border-surface-border p-4 text-[11px] text-surface-muted">
            Map data: OpenStreetMap. Camera locations shown here are demo coordinates for the prototype.
          </div>
        </div>
      </div>
    </div>
  );
}
