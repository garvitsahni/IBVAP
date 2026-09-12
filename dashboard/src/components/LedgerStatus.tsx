import { useState, useEffect } from "react";
import { api } from "../services/api";
import type { LedgerStatus as LedgerStatusType } from "../types/api";

export function LedgerStatus() {
  const [status, setStatus] = useState<LedgerStatusType | null>(null);
  useEffect(() => { api.getLedgerStatus().then(setStatus).catch(() => {}); }, []);

  if (!status) return <div className="text-neutral-400 text-sm">Checking ledger...</div>;

  return (
    <div className={`p-2 rounded text-sm font-medium ${
      status.is_valid ? "bg-system-ok/10 text-system-ok border border-system-ok/30"
                      : "bg-system-compromised/10 text-system-compromised border border-system-compromised/30"
    }`}>
      {status.is_valid ? "\u2713 Ledger Chain Verified" : `\u2717 Ledger Broken at entry #${status.broken_at_index}`}
      <span className="text-xs text-neutral-400 ml-2">({status.total_entries} entries)</span>
    </div>
  );
}
