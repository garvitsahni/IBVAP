import { useState } from "react";
import { Shield, Camera, Activity, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { AlertQueue } from "./components/AlertQueue";
import { AlertDetail } from "./components/AlertDetail";
import { CameraGrid } from "./components/CameraGrid";
import { EventLog } from "./components/EventLog";
import { SidebarStats } from "./components/SidebarStats";
import { SystemStatus } from "./components/SystemStatus";
import type { Alert } from "./types/api";

type View = "alerts" | "cameras" | "events" | "settings";

const navItems: { id: View; label: string; icon: typeof Shield }[] = [
  { id: "alerts", label: "Alerts", icon: Shield },
  { id: "cameras", label: "Cameras", icon: Camera },
  { id: "events", label: "Events", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function App() {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [view, setView] = useState<View>("alerts");
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-black">
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r border-border-subtle bg-surface-1 transition-all duration-300 ${
          collapsed ? "w-[60px]" : "w-[220px]"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center shrink-0 border border-accent/10">
            <Shield className="w-4 h-4 text-accent" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-semibold text-[13px] tracking-wide text-text-primary">
                IBVAP
              </span>
              <span className="text-[10px] text-text-muted tracking-widest uppercase">
                Surveillance
              </span>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-4 h-px bg-gradient-to-r from-transparent via-border-default to-transparent" />

        {/* Nav */}
        <nav className="flex-1 py-4 px-2 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setView(item.id);
                  setSelectedAlert(null);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                  active
                    ? "bg-accent/10 text-accent shadow-[inset_0_0_20px_-8px] shadow-accent/10"
                    : "text-text-muted hover:text-text-secondary hover:bg-white/[0.02]"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" strokeWidth={active ? 2 : 1.5} />
                {!collapsed && <span>{item.label}</span>}
                {active && !collapsed && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-accent" />
                )}
              </button>
            );
          })}
        </nav>

        {/* System Status */}
        {!collapsed && <SystemStatus />}

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center h-10 border-t border-border-subtle text-text-muted hover:text-text-secondary transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <header className="sticky top-0 z-10 flex items-center justify-between px-8 h-14 border-b border-border-subtle bg-black/80 backdrop-blur-2xl">
          <h1 className="text-[13px] font-medium text-text-primary capitalize tracking-wide">{view}</h1>
          <SidebarStats />
        </header>

        {/* Content */}
        <div className="p-8">
          {view === "alerts" && !selectedAlert && (
            <AlertQueue onSelectAlert={setSelectedAlert} />
          )}
          {view === "alerts" && selectedAlert && (
            <AlertDetail alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
          )}
          {view === "cameras" && <CameraGrid />}
          {view === "events" && <EventLog />}
          {view === "settings" && (
            <div className="flex items-center justify-center h-64">
              <p className="text-text-muted text-sm">Settings coming soon.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
