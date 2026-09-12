import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom"
import { AnimatePresence } from "framer-motion"
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

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
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
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AnimatedRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
