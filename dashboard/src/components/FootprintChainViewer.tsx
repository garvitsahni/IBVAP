import type { FootprintChain } from "../types/api";

export function FootprintChainViewer({ chain }: { chain: FootprintChain }) {
  return (
    <div className="p-3 bg-neutral-800 rounded">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-bold uppercase">Footprint Chain</span>
        <span className={`text-xs ${chain.is_valid ? "text-system-ok" : "text-system-compromised"}`}>
          {chain.is_valid ? "\u2713 Verified" : "\u2717 Broken"}
        </span>
      </div>
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {chain.entries.map((entry, i) => (
          <div key={entry.id} className="flex items-center">
            <div className="bg-neutral-700 px-2 py-1 rounded text-xs text-center min-w-[80px]">
              <div className="font-mono font-bold">{entry.camera_id}</div>
              <div className="text-neutral-400 text-[10px]">{new Date(entry.timestamp).toLocaleTimeString()}</div>
              <div className="text-[10px] text-neutral-500">{entry.event_type}</div>
            </div>
            {i < chain.entries.length - 1 && <span className="text-neutral-600 mx-1">&rarr;</span>}
          </div>
        ))}
      </div>
      <div className="mt-2 text-xs text-neutral-400">
        {chain.camera_hops} camera hops &bull; Object: <span className="font-mono">{chain.object_id}</span>
      </div>
    </div>
  );
}
