import Card from "../components/ui/Card";

// TODO: Replace with real API (Task 10)
const MOCK_CAMERAS: Array<{ id: string; label: string; status: string }> = [];

const statusStyle = {
  online: { color: "#22c55e", label: "Online" },
  offline: { color: "#ef4444", label: "Offline" },
  degraded: { color: "#f59e0b", label: "Degraded" },
};

export default function Cameras() {
  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.6rem" }}>Cameras</h1>
      <p>Registered CCTV/IP cameras and their current demo status.</p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
          marginTop: "1.25rem",
        }}
      >
        {MOCK_CAMERAS.map((camera) => {
          const status = statusStyle[camera.status] || statusStyle.offline;
          return (
            <Card key={camera.id} title={camera.label} eyebrow={camera.id}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: "50%",
                    background: status.color,
                    display: "inline-block",
                  }}
                />
                <span>{status.label}</span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
