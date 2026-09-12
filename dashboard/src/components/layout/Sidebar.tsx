import { NavLink, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  LayoutDashboard,
  Video,
  Bell,
  History,
  BarChart3,
  Map,
  Settings,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

// Assumes AuthContext exposes { user, logout() }. user is expected to look
// like { name, badgeId } — adjust the two lines in the footer if your shape differs.

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/live-monitoring', label: 'Live Monitoring', icon: Video },
  { to: '/alerts', label: 'Alerts', icon: Bell, badgeKey: 'alerts' },
  { to: '/history', label: 'Event History', icon: History },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/map', label: 'Map View', icon: Map },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar({ badgeCounts = { alerts: 0 } }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout?.();
    navigate('/login', { replace: true });
  };

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-brand-primary text-white">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">
          <ShieldCheck size={16} />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold">BorderEye</p>
          <p className="text-[10px] text-white/50">Video Analytics Platform</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, badgeKey }) => {
          const badgeCount = badgeKey ? badgeCounts[badgeKey] : 0;
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? 'bg-white/10 text-white font-medium'
                    : 'text-white/70 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <span className="flex items-center gap-2.5">
                <Icon size={16} />
                {label}
              </span>
              {badgeCount > 0 && (
                <span className="rounded-full bg-severity-critical px-1.5 py-0.5 text-[10px] font-medium text-white">
                  {badgeCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-white/10 px-4 py-4">
        <div className="mb-3 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs font-medium">
            {(user?.name || 'Officer').slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-xs font-medium">{user?.name || 'Inspector'}</p>
            <p className="truncate text-[10px] text-white/50">ID: {user?.badgeId || '—'}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-white/70 transition-colors hover:bg-white/5 hover:text-white"
        >
          <LogOut size={14} />
          Logout
        </button>
      </div>
    </aside>
  );
}
