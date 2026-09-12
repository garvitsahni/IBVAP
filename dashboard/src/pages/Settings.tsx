import { useState } from 'react';
import { Bell, Lock, User, ShieldCheck, Monitor, Save } from 'lucide-react';

export default function Settings() {
  const [notifications, setNotifications] = useState(true);
  const [criticalAlerts, setCriticalAlerts] = useState(true);
  const [compactMode, setCompactMode] = useState(false);
  const [saved, setSaved] = useState(false);

  const saveSettings = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="min-h-full bg-surface-bg p-5 text-surface-text">
      <div className="mb-5">
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} className="text-brand-primary" />
          <h1 className="text-xl font-semibold">Settings</h1>
        </div>
        <p className="mt-1 text-sm text-surface-muted">
          Manage your BorderEye account and console preferences.
        </p>
      </div>

      <div className="mx-auto max-w-3xl space-y-5">
        <section className="rounded-xl border border-surface-border bg-white shadow-card">
          <div className="flex items-center gap-3 border-b border-surface-border px-5 py-4">
            <User size={18} className="text-brand-primary" />
            <div>
              <h2 className="text-sm font-semibold">Officer Profile</h2>
              <p className="text-xs text-surface-muted">Account information</p>
            </div>
          </div>

          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-surface-muted">Officer Name</label>
              <input
                defaultValue="Border Security Officer"
                className="w-full rounded-lg border border-surface-border bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-surface-muted">Officer ID</label>
              <input
                defaultValue="BORDER-001"
                disabled
                className="w-full rounded-lg border border-surface-border bg-surface-bg px-3 py-2.5 text-sm text-surface-muted"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-surface-muted">Role</label>
              <input
                defaultValue="Security Officer"
                disabled
                className="w-full rounded-lg border border-surface-border bg-surface-bg px-3 py-2.5 text-sm text-surface-muted"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-surface-muted">Department</label>
              <input
                defaultValue="Border Surveillance"
                disabled
                className="w-full rounded-lg border border-surface-border bg-surface-bg px-3 py-2.5 text-sm text-surface-muted"
              />
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-surface-border bg-white shadow-card">
          <div className="flex items-center gap-3 border-b border-surface-border px-5 py-4">
            <Bell size={18} className="text-brand-primary" />
            <div>
              <h2 className="text-sm font-semibold">Notifications</h2>
              <p className="text-xs text-surface-muted">Control alert notifications</p>
            </div>
          </div>

          <div className="divide-y divide-surface-border">
            <SettingToggle
              icon={Bell}
              title="Enable notifications"
              description="Receive BorderEye security notifications."
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

        <section className="rounded-xl border border-surface-border bg-white shadow-card">
          <div className="flex items-center gap-3 border-b border-surface-border px-5 py-4">
            <Monitor size={18} className="text-brand-primary" />
            <div>
              <h2 className="text-sm font-semibold">Console Preferences</h2>
              <p className="text-xs text-surface-muted">Customize the monitoring console</p>
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

        <section className="rounded-xl border border-surface-border bg-white shadow-card">
          <div className="flex items-center gap-3 border-b border-surface-border px-5 py-4">
            <Lock size={18} className="text-brand-primary" />
            <div>
              <h2 className="text-sm font-semibold">Security</h2>
              <p className="text-xs text-surface-muted">Account security controls</p>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 p-5">
            <div>
              <p className="text-sm font-medium">Change password</p>
              <p className="text-xs text-surface-muted">Update your officer account password.</p>
            </div>
            <button
              type="button"
              className="rounded-lg border border-surface-border px-3 py-2 text-xs font-medium hover:bg-surface-bg"
            >
              Change
            </button>
          </div>
        </section>

        <div className="flex items-center justify-end gap-3">
          {saved && <span className="text-xs text-brand-primary">Settings saved</span>}
          <button
            type="button"
            onClick={saveSettings}
            className="flex items-center gap-2 rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-primaryLight"
          >
            <Save size={16} />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}

function SettingToggle({ icon: Icon, title, description, checked, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex items-center gap-3">
        <Icon size={16} className="text-surface-muted" />
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-surface-muted">{description}</p>
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          checked ? 'bg-brand-primary' : 'bg-surface-border'
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
