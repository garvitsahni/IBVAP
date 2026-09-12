import { Car } from 'lucide-react';

export default function ANPRDetails({ vehicle }) {
  if (!vehicle) return null;

  return (
    <div className="rounded-md border border-ops-border bg-ops-bg p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-ops-muted">
        <Car size={13} />
        ANPR Result
      </div>
      <div className="grid grid-cols-2 gap-y-2 text-sm">
        <div>
          <p className="text-[11px] text-ops-muted">Plate Number</p>
          <p className="font-mono text-ops-text tracking-wide">{vehicle.plate}</p>
        </div>
        <div>
          <p className="text-[11px] text-ops-muted">Vehicle Type</p>
          <p className="text-ops-text">{vehicle.vehicleType}</p>
        </div>
        {vehicle.color && (
          <div>
            <p className="text-[11px] text-ops-muted">Color</p>
            <p className="text-ops-text">{vehicle.color}</p>
          </div>
        )}
      </div>
    </div>
  );
}
