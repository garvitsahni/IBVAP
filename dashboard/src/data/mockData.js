// Mock data for Phase 3 + 4. Swap for real API/WebSocket calls once the backend is wired up.

export const MOCK_CAMERAS = [
  { id: 'CAM-01', label: 'Border Gate — North', status: 'online' },
  { id: 'CAM-02', label: 'Border Gate — South', status: 'online' },
  { id: 'CAM-03', label: 'Perimeter Fence A', status: 'online' },
  { id: 'CAM-04', label: 'Perimeter Fence B', status: 'offline' },
  { id: 'CAM-05', label: 'Vehicle Checkpoint', status: 'online' },
  { id: 'CAM-06', label: 'Watchtower 2', status: 'online' },
  { id: 'CAM-07', label: 'River Crossing', status: 'degraded' },
  { id: 'CAM-08', label: 'Access Road East', status: 'online' },
];

export const MOCK_ALERTS = [
  {
    id: 'AL-1042',
    cameraId: 'CAM-03',
    cameraLabel: 'Perimeter Fence A',
    type: 'Unauthorized Intrusion',
    severity: 'critical',
    timestamp: Date.now() - 1000 * 20,
    confidence: 0.94,
    status: 'new',
    location: { lat: 28.6142, lng: 77.2081, label: 'Perimeter Fence A, Sector 4' },
    snapshotLabel: 'Person detected crossing fence line',
  },
  {
    id: 'AL-1041',
    cameraId: 'CAM-05',
    cameraLabel: 'Vehicle Checkpoint',
    type: 'Unrecognized Vehicle (ANPR)',
    severity: 'high',
    timestamp: Date.now() - 1000 * 60 * 3,
    confidence: 0.88,
    status: 'new',
    location: { lat: 28.6119, lng: 77.2295, label: 'Vehicle Checkpoint, Gate 2' },
    snapshotLabel: 'Vehicle flagged — plate not in registry',
    vehicle: { plate: 'DL 4C AF 7231', vehicleType: 'SUV', color: 'White' },
  },
  {
    id: 'AL-1040',
    cameraId: 'CAM-07',
    cameraLabel: 'River Crossing',
    type: 'Feed Degraded',
    severity: 'medium',
    timestamp: Date.now() - 1000 * 60 * 8,
    confidence: 0.61,
    status: 'acknowledged',
    location: { lat: 28.598, lng: 77.246, label: 'River Crossing, North Bank' },
    snapshotLabel: 'Signal quality below threshold',
  },
  {
    id: 'AL-1039',
    cameraId: 'CAM-01',
    cameraLabel: 'Border Gate — North',
    type: 'Loitering Detected',
    severity: 'low',
    timestamp: Date.now() - 1000 * 60 * 14,
    confidence: 0.73,
    status: 'new',
    location: { lat: 28.62, lng: 77.201, label: 'Border Gate — North' },
    snapshotLabel: 'Individual stationary for 6+ minutes',
  },
  {
    id: 'AL-1038',
    cameraId: 'CAM-06',
    cameraLabel: 'Watchtower 2',
    type: 'Motion — Routine Patrol',
    severity: 'info',
    timestamp: Date.now() - 1000 * 60 * 22,
    confidence: 0.4,
    status: 'false_positive',
    location: { lat: 28.616, lng: 77.219, label: 'Watchtower 2 perimeter' },
    snapshotLabel: 'Patrol vehicle — expected motion',
    vehicle: { plate: 'DL 1A BC 4410', vehicleType: 'Patrol Jeep', color: 'Olive' },
  },
];

// Phase 5 — historical events for the event history / analytics views.
const EVENT_TYPES = [
  'Unauthorized Intrusion',
  'Unrecognized Vehicle (ANPR)',
  'Loitering Detected',
  'Motion — Routine Patrol',
  'Feed Degraded',
  'Perimeter Breach',
];

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];
const STATUSES = ['acknowledged', 'escalated', 'false_positive', 'resolved'];

function seededRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function generateMockEvents(count = 42) {
  const rand = seededRandom(7);
  const events = [];

  for (let i = 0; i < count; i++) {
    const camera = MOCK_CAMERAS[Math.floor(rand() * MOCK_CAMERAS.length)];
    const type = EVENT_TYPES[Math.floor(rand() * EVENT_TYPES.length)];
    const severity = SEVERITIES[Math.floor(rand() * SEVERITIES.length)];
    const status = STATUSES[Math.floor(rand() * STATUSES.length)];
    const daysAgo = rand() * 14;
    const timestamp = Date.now() - daysAgo * 24 * 60 * 60 * 1000;
    const isVehicleEvent = type === 'Unrecognized Vehicle (ANPR)';

    events.push({
      id: `EV-${2000 + i}`,
      cameraId: camera.id,
      cameraLabel: camera.label,
      type,
      severity,
      status,
      timestamp,
      confidence: 0.5 + rand() * 0.49,
      location: {
        lat: 28.55 + rand() * 0.12,
        lng: 77.15 + rand() * 0.15,
        label: camera.label,
      },
      snapshotLabel: `${type} at ${camera.label}`,
      ...(isVehicleEvent
        ? {
            vehicle: {
              plate: `DL ${Math.floor(1 + rand() * 9)}${String.fromCharCode(
                65 + Math.floor(rand() * 26)
              )} ${String.fromCharCode(
                65 + Math.floor(rand() * 26)
              )}${String.fromCharCode(
                65 + Math.floor(rand() * 26)
              )} ${Math.floor(1000 + rand() * 8999)}`,
              vehicleType: rand() > 0.5 ? 'Sedan' : 'SUV',
              color: rand() > 0.5 ? 'White' : 'Black',
            },
          }
        : {}),
    });
  }

  return events.sort((a, b) => b.timestamp - a.timestamp);
}

export const MOCK_EVENTS = generateMockEvents();
