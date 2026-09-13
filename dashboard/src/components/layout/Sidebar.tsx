import { NavLink, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  ShieldCheck,
  LayoutDashboard,
  Bell,
  History,
  Map,
  Settings,
  LogOut,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: 'alerts', label: 'Alerts', icon: Bell },
  { to: 'history', label: 'History', icon: History },
  { to: 'map', label: 'Map', icon: Map },
  { to: 'settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-surface">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/10">
          <ShieldCheck size={16} className="text-accent" />
        </div>
        <div>
          <p className="font-display text-sm font-semibold tracking-wide text-text-primary">IBVAP</p>
          <p className="text-[10px] text-text-muted">Surveillance</p>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-4 border-t border-border" />

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors',
                isActive
                  ? 'bg-surface-3 text-text-primary font-medium'
                  : 'text-text-secondary hover:bg-surface-2 hover:text-text'
              )
            }
          >
            <Icon size={15} className="shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-2">
        <button
          type="button"
          onClick={() => navigate('/login', { replace: true })}
          className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
        >
          <LogOut size={15} />
          Logout
        </button>
      </div>
    </aside>
  );
}
