import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider } from "@/context/AuthContext"
import { ProtectedRoute } from "@/routes/ProtectedRoute"
import { ConsoleLayout } from "@/components/layout/ConsoleLayout"
import { LoginPage } from "@/pages/LoginPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { AlertsPage } from "@/pages/AlertsPage"
import { EventHistoryPage } from "@/pages/EventHistoryPage"
import { MapPage } from "@/pages/MapPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { NotFound } from "@/pages/NotFound"

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><ConsoleLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="history" element={<EventHistoryPage />} />
            <Route path="map" element={<MapPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
