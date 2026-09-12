import { useState, useEffect } from "react";
import { Zap, Database, Cpu } from "lucide-react";

interface Health {
  status: string;
  detection_tier: string;
  ledger: { status: string };
  power_mode: string;
}

export function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    fetch("/api/v1/system/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() =>
        setHealth({ status: "unknown", detection_tier: "-", ledger: { status: "-" }, power_mode: "-" })
      );
  }, []);

  if (!health) return null;

  const statusDot = {
    ok: "bg-status-ok",
    degraded: "bg-status-degraded",
    critical: "bg-status-critical",
  }[health.status] || "bg-text-muted";

  const items = [
    { icon: Cpu, label: "Detection", value: health.detection_tier },
    { icon: Zap, label: "Power", value: health.power_mode },
    { icon: Database, label: "Ledger", value: health.ledger.status },
  ];

  return (
    <div className="px-3 py-3 border-t border-border-subtle">
      {/* Status indicator */}
      <div className="flex items-center gap-2.5 px-1 mb-3">
        <div className="relative">
          <div className={`w-2 h-2 rounded-full ${statusDot}`} />
          <div className={`absolute inset-0 w-2 h-2 rounded-full ${statusDot} animate-ping opacity-30`} />
        </div>
        <span className="text-[10px] font-semibold text-text-secondary uppercase tracking-[0.15em]">
          {health.status}
        </span>
      </div>

      {/* System details */}
      <div className="space-y-1.5">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex items-center gap-2 px-1 py-1 text-[11px]">
              <Icon className="w-3 h-3 text-text-muted" strokeWidth={1.5} />
              <span className="text-text-muted">{item.label}</span>
              <span className="ml-auto text-text-secondary font-mono tracking-wide">{item.value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
