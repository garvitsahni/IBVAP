# Task 10: Dashboard SystemHealth Component

**Files:**
- Create: `dashboard/src/components/SystemHealth.tsx`
- Modify: `dashboard/src/components/Header.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/system/health`, SSE `system_health_changed` event
- Produces: Health badge + expandable detail panel in Header

## Steps

### Step 1: Create SystemHealth.tsx

Create `dashboard/src/components/SystemHealth.tsx`:

```tsx
import { useState, useEffect } from "react";

interface SystemHealth {
  status: "ok" | "degraded" | "critical" | "unknown";
  cameras: Record<string, string>;
  detection_tier: string;
  ledger: { status: string };
  power_mode: string;
}

export function SystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch("/api/v1/system/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "unknown", cameras: {}, detection_tier: "unknown", ledger: { status: "unknown" }, power_mode: "unknown" }));
  }, []);

  useEffect(() => {
    const es = new EventSource("/api/v1/stream");
    es.addEventListener("system_health_changed", (e) => {
      const data = JSON.parse(e.data);
      setHealth((prev) => prev ? { ...prev, ...data } : data);
    });
    return () => es.close();
  }, []);

  if (!health) return null;

  const statusColor = {
    ok: "bg-green-500",
    degraded: "bg-yellow-500",
    critical: "bg-red-500",
    unknown: "bg-gray-400",
  }[health.status];

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`px-3 py-1 rounded-full text-white text-sm font-medium ${statusColor}`}
      >
        {health.status.toUpperCase()}
      </button>
      {expanded && (
        <div className="absolute right-0 mt-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 p-4 text-sm">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Detection:</span>
              <span className="text-white">{health.detection_tier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Power:</span>
              <span className="text-white">{health.power_mode}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Ledger:</span>
              <span className="text-white">{health.ledger.status}</span>
            </div>
            <div className="border-t border-gray-700 pt-2 mt-2">
              <span className="text-gray-400 text-xs">Cameras:</span>
              {Object.entries(health.cameras).map(([id, status]) => (
                <div key={id} className="flex justify-between ml-2">
                  <span className="text-gray-300">{id}</span>
                  <span className={status === "online" ? "text-green-400" : "text-red-400"}>{status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 2: Integrate SystemHealth into Header.tsx

Edit `dashboard/src/components/Header.tsx` — import and add `<SystemHealth />` in the header bar:

```tsx
import { SystemHealth } from "./SystemHealth";
// ... in the header JSX, add:
<SystemHealth />
```

### Step 3: Build dashboard to verify no type errors

Run: `cd dashboard; npm run build 2>&1 | tail -10`
Expected: build succeeds

### Step 4: Commit

```bash
git add dashboard/src/components/SystemHealth.tsx dashboard/src/components/Header.tsx
git commit -m "feat: add SystemHealth badge to dashboard header"
```
