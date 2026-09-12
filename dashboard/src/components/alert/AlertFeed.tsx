import { AnimatedList } from "@/registry/magicui/animated-list"
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
    <div className="flex flex-col gap-1">
      <AnimatedList>
        {alerts.map((alert) => (
          <AlertItem
            key={alert.id}
            alert={alert}
            isSelected={alert.id === selectedId}
            onClick={() => onSelect?.(alert)}
          />
        ))}
      </AnimatedList>
    </div>
  )
}
