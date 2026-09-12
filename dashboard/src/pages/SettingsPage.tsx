import { useState } from 'react';
import { Bell, Lock, User, ShieldCheck, Monitor, Save } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

function SettingToggle({
  icon: Icon,
  title,
  description,
  checked,
  onChange,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex items-center gap-3">
        <Icon size={16} className="text-text-secondary" />
        <div>
          <p className="text-sm font-medium text-text-primary">{title}</p>
          <p className="text-xs text-text-secondary">{description}</p>
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          checked ? 'bg-accent' : 'bg-border'
        }`}
      >
        <span
          className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-transform ${
            checked ? 'left-6' : 'left-1'
          }`}
        />
      </button>
    </div>
  );
}

export function SettingsPage() {
  const { officer } = useAuth();
  const [notifications, setNotifications] = useState(true);
  const [criticalAlerts, setCriticalAlerts] = useState(true);
  const [compactMode, setCompactMode] = useState(false);
  const [saved, setSaved] = useState(false);

  const saveSettings = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} className="text-accent" />
          <h1 className="text-lg font-semibold text-text-primary">Settings</h1>
        </div>
        <p className="mt-1 text-sm text-text-secondary">
          Manage your IBVAP account and console preferences.
        </p>
      </div>

      <div className="mx-auto max-w-3xl space-y-5">
        <section className="rounded-xl border border-border bg-surface shadow-card">
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            <User size={18} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Officer Profile</h2>
              <p className="text-xs text-text-secondary">Account information</p>
            </div>
          </div>

          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">Officer Name</label>
              <input
                defaultValue={officer?.name || 'Border Security Officer'}
                className="w-full rounded-lg border border-border bg-white px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent focus:ring-1 focus:ring-accent"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">Officer ID</label>
              <input
                defaultValue={officer?.id || 'BORDER-001'}
                disabled
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-text-muted"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">Role</label>
              <input
                defaultValue={officer?.post || 'Security Officer'}
                disabled
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-text-muted"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-text-secondary">Department</label>
              <input
                defaultValue="Border Surveillance"
                disabled
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-sm text-text-muted"
              />
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-surface shadow-card">
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            <Bell size={18} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Notifications</h2>
              <p className="text-xs text-text-secondary">Control alert notifications</p>
            </div>
          </div>

          <div className="divide-y divide-border">
            <SettingToggle
              icon={Bell}
              title="Enable notifications"
              description="Receive IBVAP security notifications."
              checked={notifications}
              onChange={setNotifications}
            />
            <SettingToggle
              icon={ShieldCheck}
              title="Critical alerts"
              description="Notify immediately when a critical threat is detected."
              checked={criticalAlerts}
              onChange={setCriticalAlerts}
            />
          </div>
        </section>

        <section className="rounded-xl border border-border bg-surface shadow-card">
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            <Monitor size={18} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Console Preferences</h2>
              <p className="text-xs text-text-secondary">Customize the monitoring console</p>
            </div>
          </div>

          <SettingToggle
            icon={Monitor}
            title="Compact mode"
            description="Use a denser layout for dashboards and event tables."
            checked={compactMode}
            onChange={setCompactMode}
          />
        </section>

        <section className="rounded-xl border border-border bg-surface shadow-card">
          <div className="flex items-center gap-3 border-b border-border px-5 py-4">
            <Lock size={18} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Security</h2>
              <p className="text-xs text-text-secondary">Account security controls</p>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 p-5">
            <div>
              <p className="text-sm font-medium text-text-primary">Change password</p>
              <p className="text-xs text-text-secondary">Update your officer account password.</p>
            </div>
            <button
              type="button"
              className="rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-2"
            >
              Change
            </button>
          </div>
        </section>

        <div className="flex items-center justify-end gap-3">
          {saved && <span className="text-xs text-accent">Settings saved</span>}
          <button
            type="button"
            onClick={saveSettings}
            className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Save size={16} />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
