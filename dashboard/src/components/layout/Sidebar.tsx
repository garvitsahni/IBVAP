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
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/history', label: 'History', icon: History },
  { to: '/map', label: 'Map', icon: Map },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10">
          <ShieldCheck size={16} className="text-accent" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-text-primary">IBVAP</p>
          <p className="text-[10px] text-text-secondary">Video Analytics Platform</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-accent/10 text-accent border-l-2 border-accent font-medium'
                  : 'text-text-secondary hover:bg-accent/5 hover:text-text-primary border-l-2 border-transparent'
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-4 py-4">
        <button
          type="button"
          onClick={() => navigate('/login', { replace: true })}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-text-secondary transition-colors hover:bg-accent/5 hover:text-text-primary"
        >
          <LogOut size={14} />
          Logout
        </button>
      </div>
    </aside>
  );
}
