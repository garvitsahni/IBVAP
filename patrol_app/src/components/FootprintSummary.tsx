import { Route, ChevronRight } from "lucide-react";
import type { FootprintChain } from "../types/api";

export function FootprintSummary({
  footprint,
}: {
  footprint: FootprintChain;
  onBack: () => void;
}) {
  return (
    <div className="space-y-4 animate-fade-in">
      {/* Path breadcrumb */}
      <div className="flex items-center gap-2 px-4 py-3 rounded-2xl bg-surface-1 border border-border-subtle">
        <Route className="w-4 h-4 text-accent shrink-0" strokeWidth={1.5} />
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {footprint.entries.map((entry, i) => (
            <span key={entry.id} className="flex items-center gap-1.5">
              <span className="text-[11px] font-mono text-text-secondary tracking-wide">
                {entry.camera_id}
              </span>
              {i < footprint.entries.length - 1 && (
                <ChevronRight className="w-3 h-3 text-text-muted shrink-0" strokeWidth={1.5} />
              )}
            </span>
          ))}
        </div>
      </div>

      {/* Object ID */}
      <div className="flex items-center justify-between px-5 py-3.5 rounded-2xl bg-surface-1 border border-border-subtle">
        <span className="text-[11px] text-text-muted uppercase tracking-[0.15em] font-semibold">Object</span>
        <span className="text-[13px] font-medium text-text-primary font-mono tracking-wide">
          {footprint.object_id}
        </span>
      </div>

      {/* Time span */}
      <div className="flex items-center justify-between px-5 py-3.5 rounded-2xl bg-surface-1 border border-border-subtle">
        <span className="text-[11px] text-text-muted uppercase tracking-[0.15em] font-semibold">First seen</span>
        <span className="text-[13px] font-medium text-text-primary font-mono tabular-nums tracking-wide">
          {footprint.first_seen ? new Date(footprint.first_seen).toLocaleTimeString() : "—"}
        </span>
      </div>
    </div>
  );
}
