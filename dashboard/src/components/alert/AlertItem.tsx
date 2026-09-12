import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera } from "lucide-react"
import { cn } from "@/lib/utils"

interface AlertItemProps {
  alert: {
    id: string
    type: string
    severity: "critical" | "high" | "medium" | "low" | "info"
    cameraId: string
    timestamp: string
    status: string
  }
  isSelected?: boolean
  onClick?: () => void
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function AlertItem({ alert, isSelected, onClick }: AlertItemProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "cursor-pointer border-l-2 px-3 py-2.5 transition-colors",
        {
          "border-l-severity-critical bg-severity-critical/5": alert.severity === "critical" && !isSelected,
          "border-l-severity-high bg-severity-high/5": alert.severity === "high" && !isSelected,
          "border-l-severity-medium": alert.severity === "medium" && !isSelected,
          "border-l-severity-low": alert.severity === "low" && !isSelected,
          "border-l-severity-info": alert.severity === "info" && !isSelected,
        },
        isSelected && "bg-surface-3 border-l-accent",
        !isSelected && "hover:bg-surface-2"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[13px] font-medium text-text-primary">{alert.type}</span>
        <StatusBadge severity={alert.severity} />
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-muted">
        <Camera size={11} />
        <span className="font-mono">{alert.cameraId}</span>
        <span className="text-border-subtle">·</span>
        <span>{timeAgo(alert.timestamp)}</span>
      </div>
    </div>
  )
}
