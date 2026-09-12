import CameraTile from './CameraTile';
import EmptyState from './EmptyState';

export default function CameraGrid({ cameras }) {
  if (!cameras?.length) {
    return (
      <div className="rounded-md border border-dashed border-ops-border">
        <EmptyState title="No camera feeds assigned to this console" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {cameras.map((camera) => (
        <CameraTile key={camera.id} camera={camera} />
      ))}
    </div>
  );
}
