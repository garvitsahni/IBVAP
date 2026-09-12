import { Navigate, useLocation } from "react-router-dom";
import Spinner from "../components/ui/Spinner";

// TODO: Replace with real auth context (Task 10)
const useAuth = () => ({ isAuthenticated: false, loading: false });

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="auth-shell">
        <Spinner label="Verifying session" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
