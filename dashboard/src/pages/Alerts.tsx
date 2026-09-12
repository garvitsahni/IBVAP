import Card from "../components/ui/Card.jsx";
import { MOCK_ALERTS } from "../data/mockData.js";

const severityColor = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#eab308",
  info: "#60a5fa",
};

export default function Alerts() {
  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.6rem" }}>Alerts</h1>
      <p>Demo threat and anomaly alerts generated from mock data.</p>

      <div style={{ display: "grid", gap: "1rem", marginTop: "1.25rem" }}>
        {MOCK_ALERTS.map((alert) => (
          <Card key={alert.id} title={alert.type} eyebrow={alert.id}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center" }}>
              <span>Camera: {alert.cameraId}</span>
              <span style={{ color: severityColor[alert.severity] || "inherit", fontWeight: 600 }}>
                {alert.severity.toUpperCase()}
              </span>
              <span>{new Date(alert.timestamp).toLocaleString()}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
