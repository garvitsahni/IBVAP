const ICON_BG = {
  primary: 'bg-brand-primary/10 text-brand-primary',
  success: 'bg-brand-secondary/10 text-brand-secondary',
  muted: 'bg-surface-border text-surface-muted',
  danger: 'bg-severity-critical/10 text-severity-critical',
};

export default function StatCard({ icon: Icon, label, value, tone = 'primary', hint }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-surface-border bg-white p-4 shadow-card">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${ICON_BG[tone]}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-xl font-semibold leading-tight text-surface-text">{value}</p>
        <p className="truncate text-xs text-surface-muted">{label}</p>
      </div>
      {hint && <span className="ml-auto shrink-0 text-[11px] text-surface-muted">{hint}</span>}
    </div>
  );
}
