import { useEffect, useRef, useState } from 'react';
import { MOCK_CAMERAS } from '../data/mockData';

const EVENT_TYPES = [
  { type: 'Unauthorized Intrusion', severity: 'critical' },
  { type: 'Unrecognized Vehicle (ANPR)', severity: 'high' },
  { type: 'Loitering Detected', severity: 'low' },
  { type: 'Motion — Routine Patrol', severity: 'info' },
  { type: 'Perimeter Breach', severity: 'critical' },
];

let counter = 2000;

function generateAlert() {
  const camera = MOCK_CAMERAS[Math.floor(Math.random() * MOCK_CAMERAS.length)];
  const event = EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)];
  counter += 1;

  return {
    id: `AL-${counter}`,
    cameraId: camera.id,
    cameraLabel: camera.label,
    type: event.type,
    severity: event.severity,
    status: 'new',
    timestamp: Date.now(),
    confidence: 0.6 + Math.random() * 0.39,
    location: { lat: 28.55 + Math.random() * 0.12, lng: 77.15 + Math.random() * 0.15, label: camera.label },
    snapshotLabel: `${event.type} at ${camera.label}`,
  };
}

export function useAlertStream({ initialAlerts = [], intervalMs = 15000, maxAlerts = 30 } = {}) {
  const [alerts, setAlerts] = useState(initialAlerts);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const timeoutRef = useRef(null);

  useEffect(() => {
    const connectTimer = setTimeout(() => setConnectionStatus('live'), 900);

    function scheduleNext() {
      const jitter = intervalMs * 0.5 + Math.random() * intervalMs;
      timeoutRef.current = setTimeout(() => {
        setAlerts((prev) => [generateAlert(), ...prev].slice(0, maxAlerts));
        scheduleNext();
      }, jitter);
    }
    scheduleNext();

    return () => {
      clearTimeout(connectTimer);
      clearTimeout(timeoutRef.current);
    };
  }, [intervalMs, maxAlerts]);

  const updateAlertStatus = (alertId, nextStatus) => {
    setAlerts((prev) => prev.map((a) => (a.id === alertId ? { ...a, status: nextStatus } : a)));
  };

  return { alerts, connectionStatus, updateAlertStatus };
}
