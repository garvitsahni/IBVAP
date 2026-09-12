import { useState } from "react";
import { Smartphone } from "lucide-react";

export function DeviceSelector({
  deviceId,
  onChange,
}: {
  deviceId: string;
  onChange: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(deviceId);

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => {
            onChange(value || "patrol-1");
            setEditing(false);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onChange(value || "patrol-1");
              setEditing(false);
            }
          }}
          autoFocus
          className="w-24 bg-surface-2 border border-border-subtle rounded-lg px-2 py-1 text-[11px] font-mono text-text-primary focus:outline-none focus:border-accent/30"
        />
      </div>
    );
  }

  return (
    <button
      onClick={() => setEditing(true)}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-surface-2 border border-border-subtle text-text-muted hover:text-text-secondary transition-all duration-200"
    >
      <Smartphone className="w-3 h-3" strokeWidth={1.5} />
      <span className="text-[10px] font-mono tracking-wide">{deviceId}</span>
    </button>
  );
}
