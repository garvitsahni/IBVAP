import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Alert, FootprintChain } from "../types/api";
import { FootprintChainViewer } from "./FootprintChainViewer";

export function AlertDetail({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const [chain, setChain] = useState<FootprintChain | null>(null);
  const [enriched, setEnriched] = useState<Alert>(alert);

  useEffect(() => {
    api.getFootprint(alert.object_id).then(setChain).catch(() => {});
    api.getAlert(alert.alert_id).then(setEnriched).catch(() => {});
  }, [alert.alert_id]);

  const handleAcknowledge = async () => {
    const updated = await api.acknowledgeAlert(alert.alert_id);
    setEnriched(updated);
  };

  return (
    <div className="border border-neutral-700 rounded-lg p-4 bg-neutral-900">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-lg font-bold">{alert.reason}</h2>
          <p className="text-sm text-neutral-400 font-mono">{alert.camera_id} &bull; {new Date(alert.timestamp).toLocaleString()}</p>
        </div>
        <button onClick={onClose} className="text-neutral-400 hover:text-white">&times;</button>
      </div>

      <div className="mb-3 p-3 bg-neutral-800 rounded">
        <span className="text-xs font-bold text-alert-standard uppercase">Deterministic Reason</span>
        <p className="mt-1">{alert.reason}</p>
      </div>

      {enriched.ai_explanation && (
        <div className="mb-3 p-3 bg-ai-enrichment/10 border border-ai-enrichment/30 rounded">
          <span className="text-xs font-bold text-ai-enrichment uppercase">AI Enrichment</span>
          <p className="mt-1 text-sm">{enriched.ai_explanation}</p>
        </div>
      )}

      {enriched.clip_path && (
        <div className="mb-3">
          <video controls className="w-full rounded" src={`/api/v1/clips/${enriched.clip_path.split("/").pop()}`} />
        </div>
      )}

      {chain && (
        <div className="mb-3">
          <FootprintChainViewer chain={chain} />
        </div>
      )}

      {enriched.status !== "acknowledged" && (
        <button onClick={handleAcknowledge} className="bg-alert-standard text-white px-4 py-2 rounded hover:brightness-110">
          Acknowledge Alert
        </button>
      )}
      {enriched.status === "acknowledged" && (
        <span className="text-system-ok text-sm font-medium">&#10003; Acknowledged</span>
      )}
    </div>
  );
}
