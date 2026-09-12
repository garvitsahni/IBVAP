import Card from "../components/ui/Card.jsx";

export default function Analytics() {
  return (
    <div className="page-content">
      <h1 style={{ fontSize: "1.6rem" }}>Analytics</h1>
      <p>Detection statistics and camera-wise performance will be visualized here.</p>

      <Card title="Coming in Phase 5" eyebrow="Charts + detection statistics">
        <p>
          Detections per camera, false-positive rate over time, and busiest
          sectors, backed by the same data as event history.
        </p>
      </Card>
    </div>
  );
}
