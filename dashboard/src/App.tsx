import { Navigate, Routes, Route } from "react-router-dom";
import ConsoleLayout from "./components/layout/ConsoleLayout.jsx";
import ProtectedRoute from "./routes/ProtectedRoute.jsx";

import LoginPage from "./pages/LoginPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import Alerts from "./pages/Alerts.jsx";
import Cameras from "./pages/Cameras.jsx";
import EventHistory from "./pages/EventHistory.jsx";
import Analytics from "./pages/Analytics.jsx";
import MapView from "./pages/MapView.jsx";
import Settings from "./pages/Settings.jsx";
import NotFound from "./pages/NotFound.jsx";

function withConsole(page) {
  return (
    <ProtectedRoute>
      <ConsoleLayout>{page}</ConsoleLayout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      <Route path="/alerts" element={withConsole(<Alerts />)} />
      <Route path="/cameras" element={withConsole(<Cameras />)} />
      <Route path="/live-monitoring" element={withConsole(<Cameras />)} />
      <Route path="/history" element={withConsole(<EventHistory />)} />
      <Route path="/analytics" element={withConsole(<Analytics />)} />
      <Route path="/map" element={withConsole(<MapView />)} />
      <Route path="/settings" element={withConsole(<Settings />)} />

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
