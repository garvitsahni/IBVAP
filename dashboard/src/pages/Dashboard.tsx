import Card from "../components/ui/Card.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const placeholderCameras = ["CAM-04", "CAM-11", "CAM-19", "CAM-22"];

export default function Dashboard() {
  const { officer } = useAuth();

  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.6rem" }}>Live monitoring dashboard</h1>
      <p>
        Welcome back, {officer?.name}. The live camera grid and real-time
        alert feed will be wired in during Phase 3.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
          marginBottom: "2rem",
        }}
      >
        {placeholderCameras.map((cam) => (
          <Card key={cam} eyebrow={cam}>
            <div
              style={{
                aspectRatio: "16 / 10",
                background: "var(--surface-raised)",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                fontSize: "0.85rem",
              }}
            >
              Feed placeholder
            </div>
          </Card>
        ))}
      </div>

      <Card title="Coming in Phase 3" eyebrow="Live feed grid + alert stream">
        <p>
          This screen will show the live RTSP camera grid on the left and a
          real-time, priority-sorted alert stream on the right, matching the
          system workflow diagram.
        </p>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <StatusBadge level="critical" />
          <StatusBadge level="medium" />
          <StatusBadge level="low" />
        </div>
      </Card>
    </div>
  );
}
