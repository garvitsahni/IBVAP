import { AlertItem } from "./AlertItem"
import { EmptyState } from "@/components/ui/EmptyState"
import { Inbox } from "lucide-react"

interface Alert {
  id: string
  type: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  cameraId: string
  timestamp: string
  status: string
  plateText?: string | null
}

interface AlertFeedProps {
  alerts: Alert[]
  selectedId?: string
  onSelect?: (alert: Alert) => void
}

export function AlertFeed({ alerts, selectedId, onSelect }: AlertFeedProps) {
  if (alerts.length === 0) {
    return <EmptyState icon={Inbox} title="No alerts" description="No active alerts at this time" />
  }

  return (
    <div className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface">
      {alerts.map((alert) => (
        <AlertItem
          key={alert.id}
          alert={alert}
          isSelected={alert.id === selectedId}
          onClick={() => onSelect?.(alert)}
        />
      ))}
    </div>
  )
}
