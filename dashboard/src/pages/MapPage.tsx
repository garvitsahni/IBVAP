import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Camera, ShieldCheck, Navigation } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Polygon, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '@/services/api';
import type { Camera as ApiCamera } from '@/types/api';

// Leaflet's default marker assets need explicit URLs when used with Vite.
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface MapCamera {
  id: string;
  name: string;
  status: 'Online' | 'Alert' | 'Offline';
  position: [number, number];
}

const FALLBACK_CAMERAS: MapCamera[] = [
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
] as [number, number][];

function cameraIcon(status: string) {
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

function mapCamera(raw: ApiCamera): MapCamera {
  const statusMap: Record<string, MapCamera['status']> = {
    online: 'Online',
    degraded: 'Alert',
    offline: 'Offline',
  };
  return {
    id: raw.camera_id,
    name: raw.name,
    status: statusMap[raw.status] || 'Offline',
    position: [28.4575, 77.028],
  };
}

export function MapPage() {
  const [cameras, setCameras] = useState<MapCamera[]>(FALLBACK_CAMERAS);

  useEffect(() => {
    api
      .getCameras()
      .then((raw) => {
        const mapped = raw.map(mapCamera);
        if (mapped.length > 0) setCameras(mapped);
      })
      .catch(() => {});
  }, []);

  const online = cameras.filter((c) => c.status === 'Online').length;
  const alerts = cameras.filter((c) => c.status === 'Alert').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="space-y-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <MapPin size={20} className="text-accent" />
            <h1 className="text-lg font-semibold text-text-primary">Map View</h1>
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            Monitor camera locations and border surveillance zones.
          </p>
        </div>

        <div className="flex gap-2 text-xs">
          <span className="rounded-lg border border-border bg-surface px-3 py-2">
            <b className="text-accent">{online}</b> Online
          </span>
          <span className="rounded-lg border border-border bg-surface px-3 py-2">
            <b className="text-severity-critical">{alerts}</b> Alert
          </span>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
        <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Navigation size={16} className="text-accent" />
              Border Surveillance Map
            </div>
            <span className="text-xs text-text-muted">Live camera positions</span>
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

              {cameras.map((camera) => (
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

              {cameras.map((camera) => (
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
              <div className="flex items-center gap-2 text-text-secondary">
                <ShieldCheck size={13} /> Secure perimeter
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface shadow-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-text-primary">Camera Locations</h2>
            <p className="mt-1 text-xs text-text-secondary">{cameras.length} registered cameras</p>
          </div>

          <div className="divide-y divide-border">
            {cameras.map((camera) => (
              <div key={camera.id} className="flex items-center gap-3 px-4 py-3">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full ${
                    camera.status === 'Alert'
                      ? 'bg-severity-critical/10 text-severity-critical'
                      : camera.status === 'Offline'
                        ? 'bg-surface-2 text-text-muted'
                        : 'bg-accent/10 text-accent'
                  }`}
                >
                  <Camera size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text-primary">{camera.name}</p>
                  <p className="font-mono text-[11px] text-text-secondary">{camera.id}</p>
                </div>
                <span
                  className={`text-[11px] font-medium ${
                    camera.status === 'Alert'
                      ? 'text-severity-critical'
                      : camera.status === 'Offline'
                        ? 'text-text-muted'
                        : 'text-accent'
                  }`}
                >
                  {camera.status}
                </span>
              </div>
            ))}
          </div>

          <div className="border-t border-border p-4 text-[11px] text-text-secondary">
            Map data: OpenStreetMap. Camera locations shown here are demo coordinates for the prototype.
          </div>
        </div>
      </div>
    </motion.div>
  );
}
