import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Card from "../components/ui/Card.jsx";
import Input from "../components/ui/Input.jsx";
import Button from "../components/ui/Button.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/dashboard";

  const [officerId, setOfficerId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!officerId || !password) {
      setError("Enter your officer ID and password.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await login(officerId, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError("Login failed. Check your credentials and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <div style={{ width: "100%", maxWidth: "380px" }}>
        <div style={{ marginBottom: "1.5rem", textAlign: "center" }}>
          <div className="mono" style={{ color: "var(--accent)", fontSize: "0.8rem" }}>
            SIH26187
          </div>
          <h1 style={{ fontSize: "1.5rem" }}>Video Analytics Console</h1>
          <p style={{ margin: 0 }}>Authorized personnel only</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} noValidate>
            <Input
              id="officerId"
              label="Officer ID"
              value={officerId}
              onChange={(e) => setOfficerId(e.target.value)}
              placeholder="e.g. OFC-1042"
              required
            />
            <Input
              id="password"
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              required
              error={error}
            />
            <Button type="submit" variant="primary" fullWidth disabled={submitting}>
              {submitting ? "Verifying..." : "Log in"}
            </Button>
          </form>
        </Card>

        <p style={{ textAlign: "center", marginTop: "1rem", fontSize: "0.8rem" }}>
          Demo build — any officer ID and password will work.
        </p>
      </div>
    </div>
  );
}
