import { useState, useEffect } from "react";
import { Route, ShieldCheck, ShieldAlert, ChevronRight, AlertTriangle } from "lucide-react";
import { api } from "../services/api";
import type { FootprintChain } from "../types/api";
import { formatTime, formatRelative } from "../lib/time";
import { TrajectoryMap } from "./TrajectoryMap";

type LoadState = "loading" | "ready" | "notfound" | "error";

type FetchResult =
  | { key: string; ok: true; chain: FootprintChain }
  | { key: string; ok: false; notfound: boolean };

export function FootprintSummary({ objectId }: { objectId: string }) {
  const [result, setResult] = useState<FetchResult | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${objectId}#${attempt}`;

  useEffect(() => {
    let alive = true;
    api
      .getFootprint(objectId)
      .then((c) => {
        if (alive) setResult({ key, ok: true, chain: c });
      })
      .catch((e) => {
        if (!alive) return;
        const msg = e instanceof Error ? e.message : String(e);
        setResult({ key, ok: false, notfound: msg.includes("404") });
      });
    return () => {
      alive = false;
    };
  }, [objectId, attempt, key]);

  // Derive load state from whether the stored result matches the current request
  const fresh = result !== null && result.key === key;
  const state: LoadState = !fresh
    ? "loading"
    : result!.ok
    ? "ready"
    : result!.notfound
    ? "notfound"
    : "error";
  const chain = fresh && result!.ok ? result!.chain : null;

  if (state === "loading") {
    return (
      <div className="card rounded-2xl p-5 animate-fade-in">
        <div className="h-4 w-40 rounded bg-bg-elevated animate-shimmer mb-4" />
        <div className="h-24 rounded-xl bg-bg-elevated/50 animate-shimmer" />
      </div>
    );
  }

  if (state === "notfound") {
    return (
      <div className="card rounded-2xl p-6 animate-fade-in text-center">
        <Route className="w-8 h-8 text-text-muted mx-auto mb-3 opacity-40" strokeWidth={1.5} />
        <p className="text-[13px] font-medium text-text-secondary">No footprint chain recorded</p>
        <p className="text-[11px] text-text-muted mt-1.5 leading-relaxed max-w-xs mx-auto">
          Object <span className="font-mono">{objectId.slice(0, 12)}</span> has no hash-chained camera hops on this server. The chain is written synchronously when the object crosses camera zones.
        </p>
      </div>
    );
  }

  if (state === "error" || !chain) {
    return (
      <div className="card rounded-2xl p-6 animate-fade-in text-center">
        <AlertTriangle className="w-8 h-8 text-severity-high mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-[13px] font-medium text-text-secondary">Couldn&apos;t load footprint chain</p>
        <button
          onClick={() => setAttempt((n) => n + 1)}
          className="mt-3 px-4 py-2 rounded-xl bg-bg-elevated border border-border-subtle text-[12px] text-text-secondary hover:text-text-primary hover:border-border-strong transition-all"
        >
          Retry
        </button>
      </div>
    );
  }

  const valid = chain.is_valid;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Chain integrity + object */}
      <div className="card rounded-2xl p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <Route className="w-4 h-4 text-accent shrink-0" strokeWidth={1.8} />
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted">Footprint chain</p>
              <p className="text-[13px] font-medium text-text-primary font-mono truncate">{chain.object_id}</p>
            </div>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase border shrink-0 ${
              valid
                ? "bg-status-ok/10 text-status-ok border-status-ok/30"
                : "bg-severity-critical/10 text-severity-critical border-severity-critical/40"
            }`}
            title={valid ? "Hash chain verified" : "Hash chain verification FAILED — tamper evidence"}
          >
            {valid ? <ShieldCheck className="w-3 h-3" strokeWidth={2} /> : <ShieldAlert className="w-3 h-3" strokeWidth={2} />}
            {valid ? "Chain verified" : "Chain broken"}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Hops", value: String(chain.camera_hops) },
            { label: "First seen", value: chain.first_seen ? formatTime(chain.first_seen) : "—" },
            { label: "Last seen", value: chain.last_seen ? formatRelative(chain.last_seen) : "—" },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl bg-bg-elevated/50 border border-border-hairline px-3 py-2.5 text-center">
              <p className="text-[9px] uppercase tracking-[0.15em] text-text-muted mb-1">{stat.label}</p>
              <p className="text-[14px] font-semibold text-text-primary font-mono tabular-nums">{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Hop timeline: where it came from / where it went */}
      <div className="card rounded-2xl p-5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted mb-4">Camera path</p>
        {chain.entries.length === 0 ? (
          <p className="text-[12px] text-text-muted">Chain exists but no hops recorded yet.</p>
        ) : (
          <div className="relative">
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border-subtle" />
            <div className="space-y-3.5">
              {chain.entries.map((entry, i) => {
                const isLast = i === chain.entries.length - 1;
                return (
                  <div key={entry.id} className="relative flex items-start gap-3 pl-0">
                    <div
                      className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-0.5 z-10"
                      style={{
                        borderColor: isLast ? "var(--color-status-ok)" : "var(--color-accent)",
                        backgroundColor: isLast ? "var(--color-status-ok)" : "var(--color-bg-card)",
                      }}
                    />
                    <div className="min-w-0 flex-1 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-text-primary font-mono">{entry.camera_id}</p>
                        <p className="text-[10px] text-text-muted mt-0.5">{entry.event_type}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-[12px] text-text-secondary font-mono tabular-nums">{formatTime(entry.timestamp)}</p>
                        <p className="text-[9px] text-text-muted font-mono">#{entry.id}</p>
                      </div>
                    </div>
                    {!isLast && (
                      <ChevronRight className="w-3 h-3 text-text-muted absolute -bottom-4 left-[1px]" strokeWidth={1.5} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Trajectory visualization */}
      <TrajectoryMap chain={chain} />
    </div>
  );
}
