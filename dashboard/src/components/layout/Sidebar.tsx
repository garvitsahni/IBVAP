import { NavLink, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { PulsatingDot } from '@/registry/magicui/pulsating-dot';
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
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-border bg-gradient-to-b from-surface to-surface-2">
      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-3 px-5 py-5"
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 shadow-lg shadow-accent/5">
          <ShieldCheck size={18} className="text-accent" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold tracking-wide text-text">IBVAP</p>
          <p className="flex items-center gap-1.5 text-[10px] text-text-muted">
            <PulsatingDot size={5} color="#22c55e" />
            Surveillance Active
          </p>
        </div>
      </motion.div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }, index) => (
          <motion.div
            key={to}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: 0.1 + index * 0.05 }}
          >
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-all duration-200',
                  isActive
                    ? 'bg-accent/10 text-accent shadow-sm shadow-accent/5 font-medium'
                    : 'text-text-secondary hover:bg-surface-3 hover:text-text border-l-2 border-transparent'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={cn("transition-transform duration-200 group-hover:scale-110", isActive && "text-accent")} />
                  {label}
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-indicator"
                      className="ml-auto h-1.5 w-1.5 rounded-full bg-accent"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                </>
              )}
            </NavLink>
          </motion.div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-4 py-4">
        <motion.button
          type="button"
          whileHover={{ x: 2 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => navigate('/login', { replace: true })}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-xs text-text-secondary transition-colors hover:bg-severity-critical/10 hover:text-severity-critical"
        >
          <LogOut size={14} />
          Logout
        </motion.button>
      </div>
    </aside>
  );
}
