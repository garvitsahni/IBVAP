import Button from "../components/ui/Button.jsx";

export default function NotFound() {
  return (
    <div className="page-content" style={{ textAlign: "center", paddingTop: "4rem" }}>
      <h1 style={{ fontSize: "1.8rem" }}>Page not found</h1>
      <p style={{ margin: "0 auto 1.5rem" }}>
        The screen you're looking for doesn't exist or may have moved.
      </p>
      <Button to="/dashboard" variant="primary">Back to dashboard</Button>
    </div>
  );
}
