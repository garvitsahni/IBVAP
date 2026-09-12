import { Navigate, Routes, Route } from "react-router-dom";
import { ConsoleLayout } from "./components/layout/ConsoleLayout";
import ProtectedRoute from "./routes/ProtectedRoute";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import Alerts from "./pages/Alerts";
import Cameras from "./pages/Cameras";
import EventHistory from "./pages/EventHistory";
import Analytics from "./pages/Analytics";
import MapView from "./pages/MapView";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ConsoleLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="cameras" element={<Cameras />} />
        <Route path="history" element={<EventHistory />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
